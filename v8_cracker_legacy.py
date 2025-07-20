import struct

from v8_cracker import UINT64_MASK, RNGStateConverter, RngType, V8Cracker

# The exponent part of a double-precision float representing 1.0.
# This is used for converting between integer states and doubles.
EXPONENT_MASK = struct.unpack("<Q", struct.pack("<d", 1.0))[0]  # 0x3FF0000000000000


class BinaryCastConverter(RNGStateConverter):
    """Converts state to a double by casting the upper 52 bits.

    This method is used in older versions of V8.
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
        recovered_state = state_with_exponent << cls.get_ignored_lower_bits()
        return recovered_state & UINT64_MASK


class V8CrackerLegacy(V8Cracker):
    """A V8Cracker that uses the older binary casting conversion method.

    This class extends V8Cracker and overrides the converter to use
    BinaryCastConverter, which is necessary for cracking `Math.random()` values
    from older versions of the V8 engine.
    """

    rng_type = RngType.V8_LEGACY
    converter = BinaryCastConverter
