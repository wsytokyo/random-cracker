"""
Tests for the utility functions and classes in v8_random_utils.py.
"""

from v8_random_utils import (
    UINT64_MASK,
    BinaryCastConverter,
    DivisionConverter,
    XorShift128,
)


def test_binary_cast_converter():
    """Verifies that BinaryCastConverter's from_double inverts to_double."""
    converter = BinaryCastConverter()
    # Use a known state where the lower 12 bits are zero
    original_state = (0x123456789ABCDEF0 << 12) & UINT64_MASK
    random_val = converter.to_double(original_state)
    recovered_state = converter.from_double(random_val)

    # The recovered state should match the original, ignoring the unknown lower 12 bits.
    assert (original_state & ~0xFFF) == (recovered_state & ~0xFFF)


def test_division_converter():
    """Verifies that DivisionConverter's from_double inverts to_double."""
    converter = DivisionConverter()
    # Use a known state where the lower 11 bits are zero
    original_state = (0x123456789ABCDEF0 << 11) & UINT64_MASK
    random_val = converter.to_double(original_state)
    recovered_state = converter.from_double(random_val)

    # The recovered state should match the original, ignoring the unknown lower 11 bits.
    assert (original_state & ~0x7FF) == (recovered_state & ~0x7FF)


def test_xor_shift_128_inverse():
    """Verifies that XorShift128.previous_state is the inverse of next_state."""
    s0_orig, s1_orig = 0x123456789ABCDEF0, 0xFEDCBA9876543210
    s0_next, s1_next = XorShift128.next_state(s0_orig, s1_orig)
    s0_recovered, s1_recovered = XorShift128.previous_state(s0_next, s1_next)

    assert s0_orig == s0_recovered
    assert s1_orig == s1_recovered
