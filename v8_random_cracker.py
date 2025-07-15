"""
Cracks V8's Math.random() PRNG by predicting its future outputs.

This script uses the Z3 theorem prover to solve for the internal state of V8's
xorshift128+ pseudo-random number generator, given a sequence of its outputs.
Once the state is known, it can predict all future values.

It handles two different state-to-double conversion methods used by V8 over time.
"""

from z3 import BitVec, LShR, Solver, sat

from v8_random_utils import BinaryCastConverter, DivisionConverter, XorShift128


class V8RandomCracker:
    """A class to crack V8's Math.random() and predict its outputs."""

    def __init__(self):
        """Initializes the cracker, defaulting to the division converter."""
        # Start with the converter for newer V8 versions.
        # See: https://github.com/v8/v8/commit/e0609ce60acf83df5c6ecd8f1e02f771e9fc6538
        self._converter = DivisionConverter()
        self._solver = Solver()
        # We only need to track the two most recent state variables to build the constraints.
        self._var_s0 = None
        self._var_s1 = None
        self._observed_sequence = []

    def add_observed_outputs(self, sequence):
        """Adds a sequence of observed random numbers to the solver."""
        for element in sequence:
            self._add_one_observation(element)

    def _add_one_observation(self, observed_double):
        """Adds a single observed random number as a constraint to the solver."""
        # Create a new Z3 variable for the state that generated the current observation.
        var_s0_current = BitVec(f"s_{len(self._observed_sequence)}", 64)

        # Add a constraint based on the known upper bits from the observed double.
        shift = self._converter.get_ignored_lower_bits()
        known_bits = self._converter.from_double(observed_double) >> shift
        self._solver.add(LShR(var_s0_current, shift) == known_bits)

        # If we have at least two previous state variables, we can link them.
        # The xorshift128+ state transition is: s_next = f(s_current, s_previous).
        # We add the inverse constraint to the solver:
        # s_previous_previous = f(s_current, s_previous)
        if self._var_s0 is not None and self._var_s1 is not None:
            # This formula is the inverse of the xorshift128+ state transition.
            # It calculates the state s_{i-2} from s_i and s_{i-1}.
            temp = var_s0_current  # Represents s_i
            temp ^= temp << 23
            temp ^= LShR(temp, 17)
            temp ^= self._var_s0 ^ LShR(self._var_s0, 26)  # self._var_s0 is s_{i-1}
            self._solver.add(temp == self._var_s1)  # self._var_s1 is s_{i-2}

        # Slide the window of state variables forward.
        self._var_s0, self._var_s1 = var_s0_current, self._var_s0
        self._observed_sequence.append(observed_double)

    def solve(self) -> bool:
        """Tries to solve for the PRNG state. Returns True if successful."""
        if self._solver.check() == sat:
            return True

        # If solving fails, it might be because V8 is using the older binary cast
        # converter. We switch converters and rebuild the solver from scratch.
        # This fallback allows the cracker to work on outputs from different V8 versions.
        print("DivisionConverter failed, falling back to BinaryCastConverter...")
        self._converter = BinaryCastConverter()
        self._solver = Solver()
        self._var_s0 = None
        self._var_s1 = None
        sequence = self._observed_sequence
        self._observed_sequence = []
        self.add_observed_outputs(sequence)

        return self._solver.check() == sat

    def predict_next(self, n: int):
        """Predicts the next `n` random numbers.

        This should be called only after `solve()` returns True. It generates the
        next `n` random numbers by applying the inverse state transition to the
        last known states recovered by the solver.
        """
        model = self._solver.model()
        # Get the concrete values of the last two states from the solved model.
        s0 = model.evaluate(self._var_s0).as_long()
        s1 = model.evaluate(self._var_s1).as_long()

        # Generate future values by repeatedly applying the inverse state transition.
        # This is because V8 serves numbers from its cache in LIFO order.
        for _ in range(n):
            s0, s1 = XorShift128.previous_state(s0, s1)
            yield self._converter.to_double(s0)
