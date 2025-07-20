"""
Cracks V8's `Math.random()` by solving for the internal state of its PRNG.

This module provides a stateful cracker for V8's xorshift128+ generator. It
uses the Z3 theorem prover to incrementally solve for the generator's state by
observing its floating-point outputs.

For cracking older V8 versions, see `v8_cracker_legacy.py`.

The cracker is designed to handle the complexities of V8's `Math.random()`.
This includes its two-stage cache, which provides numbers in a LIFO (Last-In,
First-Out) order, requiring the cracker to reverse this process to determine
the generator's state. It also handles the different floating-point conversion
methods used across V8 versions.
"""

from abc import ABC, abstractmethod

from z3 import BitVec, LShR, Solver, sat

from random_cracker import (
    NotEnoughDataError,
    NotSolvableError,
    RandomCracker,
    RngType,
    SolverStatus,
)

# Mask for 64-bit unsigned integers.
UINT64_MASK = (1 << 64) - 1  # 0xFFFFFFFFFFFFFFFF

# Constant for 2^53, used in the division-based conversion method.
TWO_POW_53 = 1 << 53  # 0x20000000000000

# V8's PRNG uses a cache of 64 values that is refilled periodically.
CACHE_REFILL_SIZE = 64


class RNGStateConverter(ABC):
    """An abstract base class for converting between PRNG state and double-precision floats."""

    @classmethod
    @abstractmethod
    def get_ignored_lower_bits(cls) -> int: ...

    @classmethod
    @abstractmethod
    def to_double(cls, state: int) -> float: ...

    @classmethod
    @abstractmethod
    def from_double(cls, value: float) -> int: ...


class DivisionConverter(RNGStateConverter):
    """Converts state to a double by dividing the upper 53 bits by 2^53.

    This method is used in modern versions of V8.
    """

    @classmethod
    def get_ignored_lower_bits(cls) -> int:
        return 11

    @classmethod
    def to_double(cls, state: int) -> float:
        state_upper_53_bits = state >> cls.get_ignored_lower_bits()
        return float(state_upper_53_bits) / TWO_POW_53

    @classmethod
    def from_double(cls, value: float) -> int:
        state_upper_53_bits = int(value * TWO_POW_53)
        recovered_state = state_upper_53_bits << cls.get_ignored_lower_bits()
        return recovered_state & UINT64_MASK


class XorShift128PlusUtil:
    """A utility class for the xorshift128+ algorithm."""

    @classmethod
    def next_state(cls, s0: int, s1: int) -> tuple[int, int]:
        s0_next = s1
        s1_next = s0
        s1_next ^= (s1_next << 23) & UINT64_MASK
        s1_next ^= s1_next >> 17
        s1_next ^= s0_next
        s1_next ^= s0_next >> 26
        return s0_next, s1_next

    @classmethod
    def previous_state(cls, s0_next: int, s1_next: int) -> tuple[int, int]:
        s1_prev = s0_next
        temp = s1_next ^ s1_prev ^ (s1_prev >> 26)
        temp = temp ^ (temp >> 17) ^ (temp >> 34) ^ (temp >> 51)
        s0_prev = (temp ^ (temp << 23) ^ (temp << 46)) & UINT64_MASK
        return s0_prev, s1_prev


class V8Cracker(RandomCracker[float]):
    """Cracks V8's `Math.random()` by incrementally solving for its state.

    This class implements a state machine to handle the complexities of V8's
    PRNG, including its two-stage cache. The cracking process proceeds as
    follows:

    1.  `SOLVING`: The cracker collects observed values and adds them as
        constraints to the Z3 solver. Once enough values are collected (typically
        two), the solver can determine the PRNG's internal state.

    2.  `SOLVED_BEFORE_CACHE_REFILL`: The state is solved, but V8's cache may not
        have been refilled yet. Predictions are possible, but a cache refill
        could invalidate the solution.

    3.  `SOLVED`: The state is solved, and the cache has been refilled. The
        cracker can now reliably predict all future outputs.

    4.  `CACHE_REFILLED_WHILE_SOLVING`: A cache refill was detected before a
        solution could be found. The cracker discards old constraints and
        continues solving with new values.
    """

    rng_type = RngType.V8
    converter = DivisionConverter

    # --- Public API ---

    def __init__(self):
        self._status = SolverStatus.SOLVING
        self._solver = Solver()
        self._solver.push()  # For lightweight solver resets
        self._s0_sym = BitVec("s0", 64)
        self._s1_sym = BitVec("s1", 64)
        self._s0_val: int = 0
        self._s1_val: int = 0
        self._cache_refill_counter: int = 0
        self._observed_values: list[float] = []

    @property
    def status(self) -> SolverStatus:
        return self._status

    def add_value(self, new_value: float) -> None:
        self._observed_values.append(new_value)
        handler = self._get_state_handler()
        handler(new_value)

    def predict_next(self) -> float:
        match self.status:
            case SolverStatus.SOLVING | SolverStatus.CACHE_REFILLED_WHILE_SOLVING:
                raise NotEnoughDataError()
            case SolverStatus.SOLVED_BEFORE_CACHE_REFILL:
                result = self._peek_next_prediction()
                self._rotate_state()
                return result
            case SolverStatus.SOLVED:
                self._cache_refill_counter -= 1
                if self._cache_refill_counter == 0:
                    self._handle_cache_refill()
                result = self._peek_next_prediction()
                self._rotate_state()
                return result
            case SolverStatus.NOT_SOLVABLE:
                raise NotSolvableError()

    # --- State Handlers ---

    def _get_state_handler(self):
        return {
            SolverStatus.SOLVING: self._handle_solving,
            SolverStatus.CACHE_REFILLED_WHILE_SOLVING: self._handle_cache_refilled_while_solving,
            SolverStatus.SOLVED_BEFORE_CACHE_REFILL: self._handle_solved_before_cache_refill,
            SolverStatus.SOLVED: self._handle_solved,
            SolverStatus.NOT_SOLVABLE: self._handle_not_solvable,
        }[self.status]

    def _handle_solving(self, new_value: float):
        if self._is_prediction_correct(new_value):
            self._rotate_state()
            self._status = SolverStatus.SOLVED_BEFORE_CACHE_REFILL
        else:
            self._add_constraint(new_value)
            if self._solver.check() != sat:
                self._status = SolverStatus.CACHE_REFILLED_WHILE_SOLVING
                return
            self._update_state_from_model()

    def _handle_cache_refilled_while_solving(self, new_value: float):
        if self._is_prediction_correct(new_value):
            self._rotate_state()
            self._cache_refill_counter = (
                CACHE_REFILL_SIZE - len(self._observed_values) + 1
            )
            self._status = SolverStatus.SOLVED
        else:
            self._add_constraint(new_value)
            while self._solver.check() != sat:
                self._pop_oldest_constraint()
            self._update_state_from_model()

    def _handle_solved_before_cache_refill(self, new_value: float):
        if self._is_prediction_correct(new_value):
            self._rotate_state()
        else:
            self._handle_cache_refill()
            self._status = SolverStatus.SOLVED
            if not self._is_prediction_correct(new_value):
                self._status = SolverStatus.NOT_SOLVABLE
                raise NotSolvableError()
            self._rotate_state()

    def _handle_solved(self, new_value: float):
        self._cache_refill_counter -= 1
        if self._cache_refill_counter == 0:
            self._handle_cache_refill()
        if self._is_prediction_correct(new_value):
            self._rotate_state()
        else:
            self._status = SolverStatus.NOT_SOLVABLE
            raise NotSolvableError()

    def _handle_not_solvable(self, new_value: float):
        raise NotSolvableError()

    # --- Internal Helper Methods ---

    def _add_constraint(self, new_val: float):
        shift = self.converter.get_ignored_lower_bits()
        known_bits = self.converter.from_double(new_val) >> shift
        self._solver.add(LShR(self._s0_sym, shift) == known_bits)
        self._rotate_symbolic_state()

    def _pop_oldest_constraint(self) -> None:
        # reset the solver
        self._solver.pop()
        self._solver.push()
        # recover the constraints except the oldest one
        self._s0_sym = BitVec("s0", 64)
        self._s1_sym = BitVec("s1", 64)
        self._observed_values = self._observed_values[1:]
        for val in self._observed_values:
            self._add_constraint(val)

    def _update_state_from_model(self):
        model = self._solver.model()
        if len(model) == 2:
            self._s0_val = model.evaluate(self._s0_sym).as_long()
            self._s1_val = model.evaluate(self._s1_sym).as_long()

    def _rotate_state(self) -> None:
        self._s0_val, self._s1_val = XorShift128PlusUtil.previous_state(
            self._s0_val, self._s1_val
        )

    def _rotate_symbolic_state(self):
        self._s1_sym, temp = self._s0_sym, self._s1_sym
        temp ^= self._s1_sym ^ LShR(self._s1_sym, 26)
        temp ^= LShR(temp, 17) ^ LShR(temp, 34) ^ LShR(temp, 51)
        temp ^= (temp << 23) ^ (temp << 46)
        self._s0_sym = temp

    def _peek_next_prediction(self) -> float:
        return self.converter.to_double(self._s0_val)

    def _is_prediction_correct(self, new_value: float) -> bool:
        return self._peek_next_prediction() == new_value

    def _handle_cache_refill(self) -> None:
        for _ in range(CACHE_REFILL_SIZE * 2):
            self._s0_val, self._s1_val = XorShift128PlusUtil.next_state(
                self._s0_val, self._s1_val
            )
        self._cache_refill_counter = CACHE_REFILL_SIZE
