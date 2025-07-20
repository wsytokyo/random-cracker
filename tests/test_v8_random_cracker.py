import subprocess

import pytest

from v8_cracker import (
    UINT64_MASK,
    DivisionConverter,
    V8Cracker,
    XorShift128PlusUtil,
    SolverStatus,
)
from v8_cracker_legacy import BinaryCastConverter, V8CrackerLegacy


def test_binary_cast_converter():
    """Verifies that BinaryCastConverter's from_double inverts to_double."""
    # Use a known state where the lower 12 bits are zero
    original_state = (0x123456789ABCDEF0 << 12) & UINT64_MASK
    random_val = BinaryCastConverter.to_double(original_state)
    recovered_state = BinaryCastConverter.from_double(random_val)

    # The recovered state should match the original, ignoring the unknown lower 12 bits.
    assert (original_state & ~0xFFF) == (recovered_state & ~0xFFF)


def test_division_converter():
    """Verifies that DivisionConverter's from_double inverts to_double."""
    # Use a known state where the lower 11 bits are zero
    original_state = (0x123456789ABCDEF0 << 11) & UINT64_MASK
    random_val = DivisionConverter.to_double(original_state)
    recovered_state = DivisionConverter.from_double(random_val)

    # The recovered state should match the original, ignoring the unknown lower 11 bits.
    assert (original_state & ~0x7FF) == (recovered_state & ~0x7FF)


def test_xor_shift_128_inverse():
    """Verifies that XorShift128PlusUtil.previous_state is the inverse of next_state."""
    s0_orig, s1_orig = 0x123456789ABCDEF0, 0xFEDCBA9876543210
    s0_next, s1_next = XorShift128PlusUtil.next_state(s0_orig, s1_orig)
    s0_recovered, s1_recovered = XorShift128PlusUtil.previous_state(s0_next, s1_next)

    assert s0_orig == s0_recovered
    assert s1_orig == s1_recovered


def test_v8_cracker_legacy():
    """Verifies the legacy cracker with a known sequence for old V8 versions."""
    observed_sequence = [
        0.7059645842555349,
        0.08792663094382847,
        0.7988851586045023,
        0.336854523159821,
        0.07712871255601494,
    ]
    expected_predictions = [
        0.21292322268831865,
        0.6202035825575369,
        0.3622407861913677,
        0.08293436061131909,
        0.5464511822883438,
    ]

    cracker = V8CrackerLegacy()
    for val in observed_sequence:
        cracker.add_value(val)
    assert cracker.status == SolverStatus.SOLVED_BEFORE_CACHE_REFILL
    predictions = [cracker.predict_next() for _ in range(len(expected_predictions))]
    assert predictions == expected_predictions


def test_v8_cracker():
    """Verifies the modern cracker with a known sequence for new V8 versions."""
    observed_sequence = [
        0.4835242132442181,
        0.750646567782529,
        0.544701479644019,
        0.4982632644639161,
        0.19140133448030294,
    ]
    expected_predictions = [
        0.9205346875124655,
        0.5470430065705328,
        0.5253121712480878,
        0.09078515940278675,
        0.2487362245629754,
    ]

    cracker = V8Cracker()
    for val in observed_sequence:
        cracker.add_value(val)

    assert cracker.status == SolverStatus.SOLVED_BEFORE_CACHE_REFILL
    predictions = [cracker.predict_next() for _ in range(len(expected_predictions))]
    assert predictions == expected_predictions


@pytest.mark.repeat(10)
def test_v8_cracker_with_live_data():
    """Verifies the cracker against live data from a running Node.js process.

    This test provides strong evidence that the cracker works against a real-world
    V8 implementation. It is repeated to test against different random seeds.
    """
    result = subprocess.run(
        ["node", "sys_pseudo_rand_gen/v8_random.js", "30"],
        capture_output=True,
        text=True,
        check=True,
    )
    full_sequence = list(map(float, result.stdout.strip().split("\n")))

    observed_sequence = full_sequence[:5]
    expected_predictions = full_sequence[5:]

    cracker = V8Cracker()
    for val in observed_sequence:
        cracker.add_value(val)

    assert cracker.status == SolverStatus.SOLVED_BEFORE_CACHE_REFILL
    predictions = [cracker.predict_next() for _ in range(len(expected_predictions))]
    assert predictions == expected_predictions


# @pytest.mark.skip
def test_v8_cracker_with_live_data_many():
    """Verifies the cracker against live data from a running Node.js process.

    This test provides strong evidence that the cracker works against a real-world
    V8 implementation. It is repeated to test against different random seeds.
    """
    result = subprocess.run(
        ["node", "sys_pseudo_rand_gen/v8_random.js", "1000"],
        capture_output=True,
        text=True,
        check=True,
    )
    full_sequence = list(map(float, result.stdout.strip().split("\n")))

    cracker = V8Cracker()
    for val in full_sequence:
        if cracker.status == SolverStatus.SOLVED:
            assert cracker.predict_next() == val
        else:
            cracker.add_value(val)
