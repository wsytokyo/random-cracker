import subprocess
import sys
from random import Random

import pytest

from mt19937_cracker import N
from random_cracker import (
    NotEnoughDataError,
    NotSolvableError,
    RandomCracker,
    RngType,
    SolverStatus,
)


@pytest.mark.repeat(10)
def test_mt19937_cracker_predicts_future_outputs():
    """Verifies that the cracker can predict future outputs of a generator."""
    # Generate N + 1000 random numbers from random.Random.
    rnd = Random()
    num_to_generate = N + 1000
    full_sequence = [rnd.getrandbits(32) for _ in range(num_to_generate)]

    # Consume some random numbers first to show that the predictor doesn't depend on the starting point of observation.
    full_sequence = full_sequence[full_sequence[0] % 100 :]

    # Split the sequence into observed outputs and expected predictions.
    observed_sequence = full_sequence[:N]
    expected_predictions = full_sequence[N:]

    # Instantiate the cracker.
    cracker = RandomCracker.create(RngType.MT19937)

    # Add observed outputs to the cracker.
    for val in observed_sequence:
        cracker.add_value(val)

    # Verify that the cracker has solved the state.
    assert cracker.status == SolverStatus.SOLVED

    # Verify that the cracker can predict future outputs.
    predictions = [cracker.predict_next() for _ in range(len(expected_predictions))]
    assert predictions == expected_predictions


@pytest.mark.repeat(10)
def test_mt19937_cracker_with_live_data_bits32():
    """Verifies the cracker against live data from another Python process.
    This test provides strong evidence that the cracker works against a real-world Mersenne Twister implementation.
    """
    # Generate N + 1000 random numbers from an external Python script.
    num_to_generate = N + 1000
    result = subprocess.run(
        [
            sys.executable,
            "sys_pseudo_rand_gen/py_random_bits32.py",
            str(num_to_generate),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    full_sequence = list(map(int, result.stdout.strip().split("\n")))

    # Consume some random numbers first to show that the predictor doesn't depend on the starting point of observation.
    full_sequence = full_sequence[full_sequence[0] % 100 :]

    # Split the sequence into observed outputs and expected predictions.
    observed_sequence = full_sequence[:N]
    expected_predictions = full_sequence[N:]

    # Instantiate the cracker.
    cracker = RandomCracker.create(RngType.MT19937)

    # Add observed outputs to the cracker.
    for val in observed_sequence:
        cracker.add_value(val)

    # Verify that the cracker has solved the state.
    assert cracker.status == SolverStatus.SOLVED

    # Verify that the cracker can predict future outputs.
    predictions = [cracker.predict_next() for _ in range(len(expected_predictions))]
    assert predictions == expected_predictions


def test_not_enough_data_error():
    """Verifies that calling predict_next before the state is solved raises NotEnoughDataError."""
    cracker = RandomCracker.create(RngType.MT19937)
    with pytest.raises(NotEnoughDataError, match="Not enough data to predict."):
        cracker.predict_next()
    assert cracker.status == SolverStatus.SOLVING


def test_not_solvable_error():
    """Verifies that the cracker enters and stays in a NOT_SOLVABLE state with invalid input."""
    cracker = RandomCracker.create(RngType.MT19937)
    with pytest.raises(
        NotSolvableError, match="The PRNG state is not solvable with the given values."
    ):
        for _ in range(N):
            cracker.add_value(0)
        cracker.add_value(1)
    assert cracker.status == SolverStatus.NOT_SOLVABLE

    with pytest.raises(
        NotSolvableError, match="The PRNG state is not solvable with the given values."
    ):
        cracker.predict_next()
    assert cracker.status == SolverStatus.NOT_SOLVABLE

    with pytest.raises(
        NotSolvableError, match="The PRNG state is not solvable with the given values."
    ):
        cracker.add_value(0)
    assert cracker.status == SolverStatus.NOT_SOLVABLE
