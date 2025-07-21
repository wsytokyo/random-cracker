from _random import Random

from random_cracker import (
    NotEnoughDataError,
    NotSolvableError,
    RandomCracker,
    RngType,
    SolverStatus,
)

# These are the core parameters for the MT19937 algorithm, used by both the
# generator and the cracker. Centralizing them ensures consistency.
N = 624
M = 397
MATRIX_A = 0x9908B0DF
UPPER_MASK = 0x80000000
LOWER_MASK = 0x7FFFFFFF

# A 32-bit mask (all bits set to 1).
UINT32_MASK = (1 << 32) - 1  # 0xFFFFFFFF

# Tempering parameters
TEMPERING_U, TEMPERING_D = 11, UINT32_MASK
TEMPERING_S, TEMPERING_B = 7, 0x9D2C5680
TEMPERING_T, TEMPERING_C = 15, 0xEFC60000
TEMPERING_L = 18

# Constants for generating 53-bit random floats in [0.0, 1.0)
# These are used in the `random()` method to match CPython's behavior.
RANDOM_SHIFT_A = 5
RANDOM_SHIFT_B = 6
RANDOM_MULTIPLIER = 67108864.0  # 2**26
RANDOM_DIVISOR = 9007199254740992.0  # 2**53


class MT19937Cracker(RandomCracker[int]):
    rng_type = RngType.MT19937

    def __init__(self):
        self._status = SolverStatus.SOLVING
        self._state = []
        self._random: Random | None = None

    @property
    def status(self) -> SolverStatus:
        return self._status

    def add_value(self, new_value: int):
        handler = self._get_state_handler()
        handler(new_value)

    def predict_next(self) -> int:
        match self.status:
            case SolverStatus.SOLVING:
                raise NotEnoughDataError()
            case SolverStatus.SOLVED:
                return self._random.getrandbits(32)
            case _:
                raise NotSolvableError()

    # --- State Handlers ---

    def _get_state_handler(self):
        return {
            SolverStatus.SOLVING: self._handle_solving,
            SolverStatus.SOLVED: self._handle_solved,
            SolverStatus.NOT_SOLVABLE: self._handle_not_solvable,
        }[self.status]

    def _handle_solving(self, new_value: int):
        self._state.append(self._untemper(new_value))
        if len(self._state) == N:
            self._random = self._create_random(tuple(self._state + [N]))
            self._status = SolverStatus.SOLVED

    def _handle_solved(self, new_value: int):
        # consume the next value and validate it
        if self._random.getrandbits(32) != new_value:
            self._status = SolverStatus.NOT_SOLVABLE
            raise NotSolvableError()

    def _handle_not_solvable(self, new_value: int):
        raise NotSolvableError()

    # --- Internal Helper Methods ---

    @classmethod
    def _create_random(cls, state) -> Random:
        r = Random()
        r.setstate(state)
        return r

    @classmethod
    def _untemper(cls, y):
        """Reverses the tempering function of MT19937 to find the raw state."""
        y = cls._untemper_right_shift(y, TEMPERING_L)
        y = cls._untemper_left_shift(y, TEMPERING_T, TEMPERING_C)
        y = cls._untemper_left_shift(y, TEMPERING_S, TEMPERING_B)
        y = cls._untemper_right_shift(y, TEMPERING_U, TEMPERING_D)
        return y

    @classmethod
    def _untemper_right_shift(cls, y, shift, mask=UINT32_MASK):
        """Reverses a right-shift tempering operation: y ^= (y >> shift) & mask.

        The reversal works by iteratively reconstructing the original bits. Since the
        right shift moves higher-order bits into lower-order positions, we can start
        with the most significant bits (which are unchanged) and use them to recover
        the next set of bits, repeating until all bits are recovered.
        """
        res = y
        # Iterate enough times to ensure all bits have been corrected.
        for _ in range(32 // shift + 1):
            res = y ^ ((res >> shift) & mask)
        return res

    @classmethod
    def _untemper_left_shift(cls, y, shift, mask):
        """Reverses a left-shift tempering operation: y ^= (y << shift) & mask.

        Similar to the right-shift reversal, this works by iteratively reconstructing
        the original bits. We start with the least significant bits (which are
        unchanged) and use them to recover the next set of bits, repeating until
        the full number is recovered.
        """
        res = y
        # Iterate enough times to ensure all bits have been corrected.
        for _ in range(32 // shift + 1):
            res = y ^ ((res << shift) & mask)
        return res
