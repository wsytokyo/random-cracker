"""
A pure Python implementation of the MT19937 Mersenne Twister PRNG and a cracker
to determine its internal state from observed outputs.

This module provides:
- MersenneTwisterGenerator: A generator that produces the same sequence of
  numbers as Python's `random.Random` for a given seed.
- MersenneTwisterCracker: A class that can reconstruct the internal state of a
  MersenneTwisterGenerator after observing 624 of its outputs.
- Helper functions to reverse the tempering process of MT19937.
"""

from z3 import *

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


class MersenneTwisterGenerator:
    """
    A pure Python implementation of CPython's internal Mersenne Twister
    (MT19937) generator. This class is designed to produce the exact same
    sequence of numbers as `random.Random` for a given integer seed.
    """

    def __init__(self, seed):
        # State
        self.mt = [0] * N
        self.mti = 0

        self.seed(seed)

    @classmethod
    def create(cls, mt, mti):
        """
        Factory method to create a MersenneTwister instance from a known state.
        This bypasses the standard seeding process.
        """
        # Use __new__ to create an instance without calling __init__
        instance = cls.__new__(cls)
        instance.mt = mt
        instance.mti = mti
        return instance

    def seed(self, a):
        """
        Initializes the generator from a seed. This mimics how CPython's
        `random.seed()` handles integer seeds.
        """

        # CPython's seed method converts the integer seed into an array of
        # 32-bit unsigned longs.
        key = []
        if a < 0:
            a = -a
        while a > 0:
            key.append(a & UINT32_MASK)
            a >>= 32
        if not key:
            key.append(0)

        self._init_by_array(key)

    def _init_by_array(self, init_key):
        """
        Replication of the init_by_array function from _randommodule.c
        """
        # First, initialize with a standard seed
        self.mt[0] = 19650218
        for i in range(1, N):
            self.mt[i] = 1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i
            self.mt[i] &= UINT32_MASK

        key_length = len(init_key)
        i = 1
        j = 0
        k = max(N, key_length)

        for _ in range(k):
            self.mt[i] = (
                (self.mt[i] ^ ((self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) * 1664525))
                + init_key[j]
                + j
            )
            self.mt[i] &= UINT32_MASK
            i += 1
            j += 1
            if i >= N:
                self.mt[0] = self.mt[N - 1]
                i = 1
            if j >= key_length:
                j = 0

        for _ in range(N - 1):
            self.mt[i] = (
                self.mt[i] ^ ((self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) * 1566083941)
            ) - i
            self.mt[i] &= UINT32_MASK
            i += 1
            if i >= N:
                self.mt[0] = self.mt[N - 1]
                i = 1

        self.mt[0] = 0x80000000  # MSB is 1; assuring non-zero initial array
        self.mti = N

    def _twist(self):
        """Generates the next N words."""
        mag01 = (0, MATRIX_A)
        for i in range(N):
            y = (self.mt[i] & UPPER_MASK) | (self.mt[(i + 1) % N] & LOWER_MASK)
            self.mt[i] = self.mt[(i + M) % N] ^ (y >> 1) ^ mag01[y & 1]

    def gen_rand_uint32(self):
        if self.mti >= N:
            self._twist()
            self.mti = 0

        y = self.mt[self.mti]
        self.mti += 1

        # Tempering
        y ^= (y >> TEMPERING_U) & TEMPERING_D
        y ^= (y << TEMPERING_S) & TEMPERING_B
        y ^= (y << TEMPERING_T) & TEMPERING_C
        y ^= y >> TEMPERING_L

        return y & UINT32_MASK

    def gen_rand_bits(self, k):
        """
        Returns a non-negative Python integer with k random bits.
        """
        if k <= 0:
            return 0

        if k <= 32:
            return self.gen_rand_uint32() >> (32 - k)

        # For k > 32, combine multiple 32-bit outputs
        num_words = (k + 31) // 32
        result = 0

        for i in range(num_words):
            rand_word = self.gen_rand_uint32()
            # For the most significant word, discard unneeded bits
            bits_in_this_word = k - (i * 32)
            if bits_in_this_word < 32:
                rand_word >>= 32 - bits_in_this_word
            # Shift the word into its correct position and combine with the result
            result |= rand_word << (i * 32)

        return result

    def random(self):
        """
        Returns the next random floating point number in the range [0.0, 1.0).
        This is based on the CPython implementation.
        """
        # Generate a 53-bit random number (27 + 26 bits)
        a = self.gen_rand_uint32() >> RANDOM_SHIFT_A
        b = self.gen_rand_uint32() >> RANDOM_SHIFT_B

        # Scale to a float in [0.0, 1.0)
        return (a * RANDOM_MULTIPLIER + b) * (1.0 / RANDOM_DIVISOR)

    def getstate(self):
        """Return the internal state of the generator."""
        return (tuple(self.mt), self.mti)

    def setstate(self, state):
        """Restore the internal state of the generator."""
        mt_tuple, mti = state
        self.mt = list(mt_tuple)
        self.mti = mti


class MersenneTwisterCracker:
    """
    Cracks the internal state of a Mersenne Twister PRNG by observing its outputs.

    After observing 624 consecutive outputs from an MT19937 generator, this
    class can reconstruct the generator's internal state array, allowing for
    the prediction of all future outputs.
    """

    @classmethod
    def crack(cls, observed_bit32s: list[int]) -> MersenneTwisterGenerator:
        """
        Reconstructs the internal state from a list of N observed outputs.
        Returns a new, seeded MersenneTwister generator.
        """
        if len(observed_bit32s) < N:
            raise ValueError(
                f"Need at least {N} outputs to crack, got {len(observed_bit32s)}"
            )

        # 1. Untemper each of the N outputs to get the raw state vector
        reconstructed_mt = [cls._untemper(y) for y in observed_bit32s[-N:]]

        # 2. Create a new generator from the recovered state using the factory method
        cracked_generator = MersenneTwisterGenerator.create(
            mt=reconstructed_mt,
            mti=N,  # Set index to N to trigger a twist on the next call
        )

        return cracked_generator

    @classmethod
    def crack_by_z3(cls, observed_bit32s: list[int]) -> MersenneTwisterGenerator:
        """
        Reconstructs the internal state from a list of N observed outputs.
        Returns a new, seeded MersenneTwister generator.

        Note: this implementation is not as fast as the `crack` method.
        """
        if len(observed_bit32s) < N:
            raise ValueError(
                f"Need at least {N} outputs to crack, got {len(observed_bit32s)}"
            )

        solver = Solver()
        observed_bit32s = observed_bit32s[-N:]
        reconstructed_mt = []
        state = BitVec("s", 32)
        # Tempering symbolically
        y = state
        y ^= (LShR(y, TEMPERING_U)) & TEMPERING_D
        y ^= (y << TEMPERING_S) & TEMPERING_B
        y ^= (y << TEMPERING_T) & TEMPERING_C
        y ^= LShR(y, TEMPERING_L)

        # crack the mt state one by one
        for i in range(N):
            solver.push()
            solver.add(y == observed_bit32s[i])
            if solver.check() != sat:
                raise RuntimeError("Failed to find a valid state.")
            reconstructed_mt.append(solver.model().evaluate(state).as_long())
            solver.pop()

        # Create a new generator from the recovered tempered state.
        cracked_generator = MersenneTwisterGenerator.create(
            mt=reconstructed_mt,
            mti=N,  # The original generator has twisted, so we must match its state.
        )
        return cracked_generator

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

    @classmethod
    def crack_from_random(
        cls, observed_floats: list[float]
    ) -> MersenneTwisterGenerator:
        solver = Solver()
        mt_size = 2 * len(observed_floats)
        full_mt = [BitVec(f"mt_{i}", 53) for i in range(mt_size)]

        for i in range(len(observed_floats)):
            # Tempering symbolically
            y1 = full_mt[2 * i]
            y2 = full_mt[2 * i + 1]
            solver.add(y1 <= UINT32_MASK)
            solver.add(y2 <= UINT32_MASK)

            y1 ^= (LShR(y1, TEMPERING_U)) & TEMPERING_D
            y1 ^= (y1 << TEMPERING_S) & TEMPERING_B
            y1 ^= (y1 << TEMPERING_T) & TEMPERING_C
            y1 ^= LShR(y1, TEMPERING_L)
            a = y1 >> RANDOM_SHIFT_A

            y2 ^= (LShR(y2, TEMPERING_U)) & TEMPERING_D
            y2 ^= (y2 << TEMPERING_S) & TEMPERING_B
            y2 ^= (y2 << TEMPERING_T) & TEMPERING_C
            y2 ^= LShR(y2, TEMPERING_L)
            b = y2 >> RANDOM_SHIFT_B

            # extend a and b from 32 bits to 53 bits
            random_53_bits = (a << 26) | b
            observed_53_bits = round(observed_floats[i] * RANDOM_DIVISOR)
            solver.add(random_53_bits == observed_53_bits)

        for i in range(N, mt_size):
            y = (full_mt[i - N] & UPPER_MASK) | (full_mt[i + 1 - N] & LOWER_MASK)
            solver.add(
                full_mt[i] == (full_mt[i + M - N] ^ (y >> 1)) ^ ((y & 1) * MATRIX_A)
            )

        res = solver.check()
        if res != sat:
            raise RuntimeError("Failed to find a valid state.", res)
        model = solver.model()
        # Create a new generator from the recovered tempered state.
        cracked_generator = MersenneTwisterGenerator.create(
            mt=[model.evaluate(y).as_long() for y in full_mt[-N:]],
            mti=N,  # The original generator has twisted, so we must match its state.
        )
        return cracked_generator
