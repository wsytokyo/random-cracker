"""
Cracks pseudo-random number generators (PRNGs) from V8 and CPython.

This module provides a unified interface for cracking the internal state of
different PRNGs by observing their outputs. It includes implementations for:

1.  V8's `Math.random()`: Uses the Z3 theorem prover to solve for the internal
    state of V8's xorshift128+ generator from a sequence of floating-point
    outputs. It can automatically handle different conversion methods used
    across V8 versions.

2.  CPython's `random` module: Uses the standard "untempering" technique to
    reconstruct the internal state of the MT19937 Mersenne Twister generator
    after observing 624 of its raw integer outputs.

Once a generator's state is cracked, all future outputs can be predicted.
"""

import enum
import random
import struct
from abc import ABC, abstractmethod

# It is recommended to install z3-solver: pip install z3-solver
from z3 import BitVec, LShR, Solver, sat

# --- V8 Cracker Constants ---
UINT64_MASK = (1 << 64) - 1
EXPONENT_MASK = 0x3FF0000000000000
TWO_POW_53 = 1 << 53

# --- Mersenne Twister Cracker Constants ---
MT_N = 624


class RngType(enum.Enum):
    V8 = 1
    MersenneTwister = 2


class SolverStatus(enum.Enum):
    WAITING_FOR_DATA = auto()
    PARTIALLY_SOLVED = auto()
    SOLVED = auto()
    NOT_SOLVABLE = auto()


class RandomCracker(ABC):
    """An abstract base class defining the interface for a PRNG cracker."""

    @staticmethod
    def create(rng_type: RngType) -> "RandomCracker":
        # class loader
        for cls in RandomCracker.__subclasses__():
            if cls.rng_type == rng_type:
                return cls()
        raise ValueError("Invalid RNG type.")

    @property
    @abstractmethod
    def rng_type(self) -> RngType:
        """Returns the type of the PRNG being cracked."""
        ...

    @property
    @abstractmethod
    def status(self) -> SolverStatus:
        """Returns the current status of the cracker."""
        ...

    @abstractmethod
    def add_observed_float(self, observed_value: float) -> SolverStatus:
        """
        Solves for the PRNG's internal state given a sequence of floating-point outputs.

        Args:
            observed_sequence: A list of observed outputs (floats for V8,
                               ints for Mersenne Twister).

        Returns:
            SolverStatus: The current status of the cracker.
        """
        ...

    @abstractmethod
    def add_observed_int(self, observed_value: int) -> SolverStatus:
        """
        Solves for the PRNG's internal state given a sequence of integer outputs.

        Args:
            observed_sequence: A list of observed outputs (ints for Mersenne Twister).

        Returns:
            SolverStatus: The current status of the cracker.
        """
        ...

    @abstractmethod
    def predict_next_float(self) -> float:
        """
        Predicts the next floating-point random number in [0.0, 1.0).
        """
        ...

    @abstractmethod
    def predict_next_int32(self) -> int:
        """
        Predicts the next random integer with a specified bit width.
        """

    @abstractmethod
    def predict_next_bits(self, bits: int) -> int:
        """
        Predicts the next random integer with a specified bit width.
        """
        ...


# region V8 Cracker Implementation
class RNGStateConverter(ABC):
    """Interface for V8's state-to-double conversion strategies."""

    @classmethod
    @abstractmethod
    def get_ignored_lower_bits(cls) -> int: ...
    @classmethod
    @abstractmethod
    def to_double(cls, state: int) -> float: ...
    @classmethod
    @abstractmethod
    def from_double(cls, value: float) -> int: ...


class BinaryCastConverter(RNGStateConverter):
    """Converter for older V8 versions using binary casting."""

    @classmethod
    def get_ignored_lower_bits(cls) -> int:
        return 12

    @classmethod
    def to_double(cls, state: int) -> float:
        state_upper = state >> cls.get_ignored_lower_bits()
        packed = struct.pack("<Q", (state_upper | EXPONENT_MASK))
        return struct.unpack("<d", packed)[0] - 1.0

    @classmethod
    def from_double(cls, value: float) -> int:
        packed = struct.pack("<d", value + 1.0)
        state_with_exp = struct.unpack("<Q", packed)[0]
        return (state_with_exp << cls.get_ignored_lower_bits()) & UINT64_MASK


class DivisionConverter(RNGStateConverter):
    """Converter for newer V8 versions using division."""

    @classmethod
    def get_ignored_lower_bits(cls) -> int:
        return 11

    @classmethod
    def to_double(cls, state: int) -> float:
        return (state >> cls.get_ignored_lower_bits()) / TWO_POW_53

    @classmethod
    def from_double(cls, value: float) -> int:
        state_upper = int(value * TWO_POW_53)
        return (state_upper << cls.get_ignored_lower_bits()) & UINT64_MASK


class XorShift128:
    """Utility class for the stateless xorshift128+ algorithm."""

    @classmethod
    def next_state(cls, s0: int, s1: int) -> tuple[int, int]:
        s0_next, s1_next = s1, s0
        s1_next ^= (s1_next << 23) & UINT64_MASK
        s1_next ^= s1_next >> 17
        s1_next ^= s0_next
        s1_next ^= s0_next >> 26
        return s0_next, s1_next

    @classmethod
    def previous_state(cls, s0_next: int, s1_next: int) -> tuple[int, int]:
        s1_prev = s0_next
        temp = s1_next ^ s1_prev ^ (s1_prev >> 26)
        temp ^= (temp >> 17) ^ (temp >> 34) ^ (temp >> 51)
        s0_prev = (temp ^ (temp << 23) ^ (temp << 46)) & UINT64_MASK
        return s0_prev, s1_prev


class V8RandomCracker(RandomCracker):
    """Cracks V8's Math.random() by solving for its xorshift128+ state."""

    def __init__(self):
        self._converter = DivisionConverter()
        self._solver = Solver()
        self._initial_s0_sym = None
        self._initial_s1_sym = None
        self._solved_s0 = None
        self._solved_s1 = None
        self._is_solved = False

    def solve(self, observed_sequence: list[float]) -> bool:
        if len(observed_sequence) < 2:
            raise ValueError("At least two observed outputs are required.")

        generation_sequence = observed_sequence[::-1]
        s0, s1 = BitVec("s0_initial", 64), BitVec("s1_initial", 64)
        self._initial_s0_sym, self._initial_s1_sym = s0, s1

        current_s0, current_s1 = s0, s1
        for val in generation_sequence:
            shift = self._converter.get_ignored_lower_bits()
            known_bits = self._converter.from_double(val) >> shift
            self._solver.add(LShR(current_s0, shift) == known_bits)
            current_s0, current_s1 = XorShift128.next_state(current_s0, current_s1)

        if self._solver.check() == sat:
            self._is_solved = True
            model = self._solver.model()
            self._solved_s0 = model.evaluate(self._initial_s0_sym).as_long()
            self._solved_s1 = model.evaluate(self._initial_s1_sym).as_long()
            return True

        print("DivisionConverter failed, falling back to BinaryCastConverter...")
        self._converter = BinaryCastConverter()
        self._solver.reset()
        return self.solve(observed_sequence)

    def predict_next_float(self, n: int):
        if not self._is_solved:
            raise RuntimeError("Must call solve() first.")
        s0, s1 = self._solved_s0, self._solved_s1
        for _ in range(n):
            s0, s1 = XorShift128.previous_state(s0, s1)
            yield self._converter.to_double(s0)

    def predict_next_int(self, n: int, bits: int = 64):
        if not self._is_solved:
            raise RuntimeError("Must call solve() first.")
        s0, s1 = self._solved_s0, self._solved_s1
        for _ in range(n):
            s0, s1 = XorShift128.previous_state(s0, s1)
            # This simulates V8's internal Next(bits) which is not directly
            # exposed via Math.random but is part of the generator class.
            yield (s0 + s1) >> (64 - bits)


# endregion


# region Mersenne Twister Cracker Implementation
class MersenneTwisterCracker(RandomCracker):
    """Cracks CPython's random module by reconstructing the MT19937 state."""

    def __init__(self):
        self._cloned_generator = None
        self._is_solved = False
        # Tempering parameters
        self.U, self.S, self.B, self.T, self.C, self.L = (
            11,
            7,
            0x9D2C5680,
            15,
            0xEFC60000,
            18,
        )

    def _untemper(self, y):
        """Reverses the tempering function of the MT19937 algorithm."""
        y ^= y >> self.L
        y ^= (y << self.T) & self.C
        # Iterative reversal for dependent bit shifts
        for _ in range(7):
            y ^= (y << self.S) & self.B
        for _ in range(3):
            y ^= y >> self.U
        return y & 0xFFFFFFFF

    def solve(self, observed_sequence: list[int]) -> bool:
        if len(observed_sequence) < MT_N:
            raise ValueError(
                f"Exactly {MT_N} consecutive integer outputs are required."
            )

        cracked_state = [self._untemper(y) for y in observed_sequence]
        state_tuple = tuple(cracked_state + [MT_N])
        full_state = (3, state_tuple, None)  # CPython's state format

        self._cloned_generator = random.Random()
        self._cloned_generator.setstate(full_state)
        self._is_solved = True
        return True

    def predict_next_float(self, n: int):
        if not self._is_solved:
            raise RuntimeError("Must call solve() first.")
        for _ in range(n):
            yield self._cloned_generator.random()

    def predict_next_int(self, n: int, bits: int = 32):
        if not self._is_solved:
            raise RuntimeError("Must call solve() first.")
        for _ in range(n):
            yield self._cloned_generator.getrandbits(bits)


# endregion


if __name__ == "__main__":
    # --- V8 Cracker Demonstration ---
    # print("--- V8 Math.random() Cracker ---")
    # v8_observed = [
    #     0.19879119020560487,
    #     0.3956565867545744,
    #     0.69745849312803,
    #     0.9663165959747051,
    #     0.8980595618690757,
    #     0.7660140798521683,
    #     0.25534085958555064,
    #     0.28907904740148815,
    #     0.16680444866624544,
    #     0.14653066042523488,
    # ]
    # v8_cracker = V8RandomCracker()
    # if v8_cracker.solve(v8_observed[:5]):
    #     print("✅ V8 state solved!")
    #     prediction = next(v8_cracker.predict_next_float(1))
    #     print(f"   Actual next float: {v8_observed[5]:.12f}")
    #     print(f"Predicted next float: {prediction:.12f}")
    #     assert abs(v8_observed[5] - prediction) < 1e-12
    #     print("🎉 V8 Prediction Successful!\n")
    # else:
    #     print("❌ V8 solving failed.\n")

    # --- Mersenne Twister Cracker Demonstration ---
    print("--- CPython random Cracker ---")
    SEED = 1337
    target_generator = random.Random(SEED)

    # Collect 624 integer outputs from the target generator
    mt_observed = [target_generator.getrandbits(32) for _ in range(MT_N)]
    print(f"Collected {len(mt_observed)} integer outputs from target.")

    mt_cracker = MersenneTwisterCracker()
    if mt_cracker.solve(mt_observed):
        print("✅ Mersenne Twister state cracked!")

        # Predict next integer
        actual_int = target_generator.getrandbits(32)
        predicted_int = next(mt_cracker.predict_next_int(1))
        print(f"   Actual next int: {actual_int}")
        print(f"Predicted next int: {predicted_int}")
        assert actual_int == predicted_int
        print("🎉 MT Integer Prediction Successful!")

        # Predict next float
        actual_float = target_generator.random()
        predicted_float = next(mt_cracker.predict_next_float(1))
        print(f"   Actual next float: {actual_float:.12f}")
        print(f"Predicted next float: {predicted_float:.12f}")
        assert abs(actual_float - predicted_float) < 1e-12
        print("🎉 MT Float Prediction Successful!")
    else:
        print("❌ MT solving failed.")
