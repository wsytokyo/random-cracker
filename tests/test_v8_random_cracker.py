"""
Tests for the V8RandomCracker class.
"""

import subprocess

import pytest

from v8_random_cracker import V8RandomCracker


def test_v8_cracker_old_v8_binary_cast(capsys):
    """Verifies the cracker's fallback to BinaryCastConverter for old V8 sequences."""
    # This sequence requires the fallback to BinaryCastConverter.
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

    cracker = V8RandomCracker()
    cracker.add_observed_outputs(observed_sequence)
    assert cracker.solve(), "Failed to solve for PRNG state with old V8 sequence."

    # Check that the fallback message was printed.
    captured = capsys.readouterr()
    assert "falling back to BinaryCastConverter" in captured.out

    predictions = list(cracker.predict_next(5))
    assert predictions == pytest.approx(expected_predictions)


def test_v8_cracker_new_v8_division():
    """Verifies the cracker works with the default DivisionConverter for new V8 sequences."""
    # This sequence should be solved directly with the default DivisionConverter.
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

    cracker = V8RandomCracker()
    cracker.add_observed_outputs(observed_sequence)
    assert cracker.solve(), "Failed to solve for PRNG state with new V8 sequence."

    predictions = list(cracker.predict_next(5))
    assert predictions == pytest.approx(expected_predictions)


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

    cracker = V8RandomCracker()
    cracker.add_observed_outputs(observed_sequence)
    assert cracker.solve(), "Failed to solve for PRNG state with live data."
    predictions = list(cracker.predict_next(len(expected_predictions)))
    assert predictions == pytest.approx(expected_predictions)


@pytest.mark.skip
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

    observed_sequence = full_sequence[:5]
    expected_predictions = full_sequence[5:]

    cracker = V8RandomCracker()
    cracker.add_observed_outputs(observed_sequence)
    assert cracker.solve(), "Failed to solve for PRNG state with live data."
    predictions = list(cracker.predict_next(len(expected_predictions)))
    assert predictions == pytest.approx(expected_predictions)
