"""
Cracks V8's Math.random() by solving for its internal PRNG state.

This module uses the Z3 theorem prover to find the internal state of V8's
xorshift128+ pseudo-random number generator, given a sequence of its outputs.
Because V8's `Math.random()` uses a LIFO cache, the observed sequence of numbers
is the reverse of the actual generation sequence. This tool accounts for this
behavior to correctly model the generator.

Once the state is known, it can predict all future (and past) values. The tool
can automatically detect and handle two different state-to-double conversion
methods that have been used in V8's history (a binary casting method and a
division-based method), making it robust across different versions.
"""

import struct
from abc import ABC, abstractmethod

# It is recommended to install z3-solver: pip install z3-solver
from z3 import BitVec, LShR, Solver, sat

# A 64-bit mask (all bits set to 1).
UINT64_MASK = (1 << 64) - 1  # 0xFFFFFFFFFFFFFFFF

# The exponent bits for a double-precision float to be in the range [1.0, 2.0).
EXPONENT_MASK = struct.unpack("<Q", struct.pack("<d", 1.0))[0]  # 0x3FF0000000000000

# Represents 2^53, used in the division-based conversion method.
TWO_POW_53 = 1 << 53  # 0x20000000000000


class RNGStateConverter(ABC):
    """An interface for converting between a PRNG's state and a double.

    V8 has used different methods to convert the 64-bit integer state of its
    PRNG to a double in the range [0, 1). This abstract base class defines
    the interface for these conversion strategies.

    See: https://github.com/v8/v8/commit/e0609ce60acf83df5c6ecd8f1e02f771e9fc6538
    """

    @classmethod
    @abstractmethod
    def get_ignored_lower_bits(cls) -> int:
        """Returns the number of lower bits ignored by the conversion."""

    @classmethod
    @abstractmethod
    def to_double(cls, state: int) -> float:
        """Converts a 64-bit integer state to a double in [0, 1)."""

    @classmethod
    @abstractmethod
    def from_double(cls, value: float) -> int:
        """Converts a double in [0, 1) back to its generating state bits."""


class BinaryCastConverter(RNGStateConverter):
    """Converter for older V8 versions that use binary casting.

    This method takes the upper 52 bits of the PRNG state, combines them with
    the exponent bits for the range [1.0, 2.0), and reinterprets the result
    as a double. Subtracting 1.0 maps this to the desired [0, 1) range.
    """

    @classmethod
    def get_ignored_lower_bits(cls) -> int:
        return 12

    @classmethod
    def to_double(cls, state: int) -> float:
        state_upper_52_bits = state >> cls.get_ignored_lower_bits()
        state_with_exponent = state_upper_52_bits | EXPONENT_MASK
        packed = struct.pack("<Q", state_with_exponent)
        random_double = struct.unpack("<d", packed)[0]
        return random_double - 1.0

    @classmethod
    def from_double(cls, value: float) -> int:
        value_plus_one = value + 1.0
        packed = struct.pack("<d", value_plus_one)
        state_with_exponent = struct.unpack("<Q", packed)[0]
        # The lower bits were discarded and are unknown, so they remain zero.
        recovered_state = state_with_exponent << cls.get_ignored_lower_bits()
        return recovered_state & UINT64_MASK


class DivisionConverter(RNGStateConverter):
    """Converter for newer V8 versions that use division.

    This method takes the upper 53 bits of the PRNG state and divides by 2^53
    to produce a double in the range [0, 1).
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
        # The lower bits were discarded and are unknown, so they remain zero.
        recovered_state = state_upper_53_bits << cls.get_ignored_lower_bits()
        return recovered_state & UINT64_MASK


class XorShift128:
    """A utility class for the xorshift128+ algorithm.

    This class provides stateless static methods for the forward `next_state`
    function and its inverse, `previous_state`. The inverse is essential for
    predicting the next value from V8's LIFO cache.
    """

    @classmethod
    def next_state(cls, s0: int, s1: int) -> tuple[int, int]:
        """Calculates the next state (s0_next, s1_next) of the PRNG."""
        s0_next = s1
        s1_next = s0
        s1_next ^= (s1_next << 23) & UINT64_MASK
        s1_next ^= s1_next >> 17
        s1_next ^= s0_next
        s1_next ^= s0_next >> 26
        return s0_next, s1_next

    @classmethod
    def previous_state(cls, s0_next: int, s1_next: int) -> tuple[int, int]:
        """Calculates the previous state (s0_prev, s1_prev) of the PRNG."""
        s1_prev = s0_next
        temp = s1_next ^ s1_prev ^ (s1_prev >> 26)
        temp = temp ^ (temp >> 17) ^ (temp >> 34) ^ (temp >> 51)
        s0_prev = (temp ^ (temp << 23) ^ (temp << 46)) & UINT64_MASK
        return s0_prev, s1_prev


class V8RandomCracker:
    """A class to crack V8's Math.random() by solving for its state."""

    def __init__(self):
        """Initializes the cracker."""
        self._converter = DivisionConverter()  # Default to the modern converter
        self._solver = Solver()
        self._initial_s0 = None
        self._initial_s1 = None
        self._is_solved = False

    def solve(self, observed_sequence: list[float]) -> bool:
        """
        Solves for the PRNG's initial state given a sequence of outputs.

        Args:
            observed_sequence: A list of consecutive numbers from Math.random().
                               At least 4-5 values are recommended.

        Returns:
            True if a solution was found, False otherwise.
        """
        if len(observed_sequence) < 2:
            raise ValueError("At least two observed outputs are required.")

        # V8's cache is LIFO, so the observed order is the reverse of the
        # generation order. We reverse it back to model the generator correctly.
        generation_sequence = observed_sequence[::-1]

        # Define the initial symbolic states that we want to find.
        s0 = BitVec("s0_initial", 64)
        s1 = BitVec("s1_initial", 64)
        self._initial_s0, self._initial_s1 = s0, s1

        # Build constraints by modeling the forward generation process.
        current_s0, current_s1 = s0, s1
        for i, val in enumerate(generation_sequence):
            # The generated double comes from the `s0` part of the state.
            # Add a constraint that the upper bits of the symbolic `current_s0` must
            # match the bits recovered from the observed double.
            shift = self._converter.get_ignored_lower_bits()
            known_bits = self._converter.from_double(val) >> shift
            self._solver.add(LShR(current_s0, shift) == known_bits)

            # Calculate the next symbolic state for the next iteration.
            s0_next = current_s1
            s1_next = current_s0
            s1_next ^= s1_next << 23
            s1_next ^= LShR(s1_next, 17)
            s1_next ^= s0_next
            s1_next ^= LShR(s0_next, 26)
            current_s0, current_s1 = s0_next, s1_next

        # Try to solve with the current converter.
        if self._solver.check() == sat:
            self._is_solved = True
            return True

        # If solving fails, fall back to the older binary cast converter.
        print("DivisionConverter failed, falling back to BinaryCastConverter...")
        self._converter = BinaryCastConverter()
        self._solver.reset()  # Clear previous constraints
        # Re-run the solve logic with the new converter.
        # This is a recursive call, but it will only happen once.
        return self.solve(observed_sequence)

    def predict_next(self, n: int):
        """
        Predicts the next `n` random numbers that will be observed.

        This must be called after `solve()` returns True. It works by finding
        the state *before* the start of the generation sequence, as this
        corresponds to the *next* number that will be popped from V8's LIFO cache.
        """
        if not self._is_solved:
            raise RuntimeError("Must call solve() successfully before predicting.")

        model = self._solver.model()
        # Get the concrete values of the initial state from the solved model.
        s0 = model.evaluate(self._initial_s0).as_long()
        s1 = model.evaluate(self._initial_s1).as_long()

        # To predict the next observed value, we need to go backwards from the
        # start of our known generation sequence.
        for _ in range(n):
            s0, s1 = XorShift128.previous_state(s0, s1)
            yield self._converter.to_double(s0)


if __name__ == "__main__":
    # --- EXAMPLE USAGE ---

    # 1. Get a sequence of random numbers from your target (e.g., Chrome console, Node.js)
    # In Chrome Console: Array.from({length: 6}, Math.random)
    # This example sequence was generated in Node.js v18.
    observed_sequence = [
        0.9311600617849973,
        0.3551442693830502,
        0.7923158995678377,
        0.787777942408997,
        0.376372264303491,
        0.23137147109312428,  # The number we want to predict
    ]

    # We will use the first 5 numbers to predict the 6th.
    input_sequence = observed_sequence[:5]
    actual_next_number = observed_sequence[5]

    print("--- V8 Math.random() Cracker ---")
    print(f"Using observed sequence: {input_sequence}")
    print("-" * 30)

    # 2. Create a cracker instance and solve for the state.
    cracker = V8RandomCracker()
    print("Solving for PRNG state...")
    if cracker.solve(input_sequence):
        print("✅ Solution found!")
        print("-" * 30)

        # 3. Predict the next number.
        print("Predicting the next number in the sequence...")
        # The predict_next() method returns a generator.
        predicted_generator = cracker.predict_next(1)
        predicted_number = next(predicted_generator)

        print(f"   Actual next number: {actual_next_number:.18f}")
        print(f"Predicted next number: {predicted_number:.18f}")

        # 4. Verify the prediction.
        if abs(actual_next_number - predicted_number) < 1e-12:
            print("\n🎉 Success! The prediction matches the actual number.")
        else:
            print("\n❌ Failure. The prediction does not match.")
    else:
        print(
            "❌ Failed to find a solution. Try providing a longer or different sequence."
        )
