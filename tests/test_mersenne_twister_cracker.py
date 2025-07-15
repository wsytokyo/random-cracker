import subprocess
import sys
from random import Random

import pytest

from mersenne_twister_cracker import MersenneTwisterCracker, MersenneTwisterGenerator, N


def test_mersenne_twister_getrandbits_32_matches_random():
    """Verifies that the output of MersenneTwisterGenerator matches random.Random."""
    seed = 123
    my_generator = MersenneTwisterGenerator(seed=seed)
    cpython_generator = Random(seed)

    for _ in range(100):
        assert my_generator.gen_rand_uint32() == cpython_generator.getrandbits(32)


def test_mersenne_twister_getrandbits_matches_random():
    """Verifies that the custom `random()` method matches `random.random()`."""
    seed = -456
    my_generator = MersenneTwisterGenerator(seed)
    cpython_generator = Random(seed)

    for _ in range(100):
        assert my_generator.gen_rand_bits(0) == cpython_generator.getrandbits(0)
        assert my_generator.gen_rand_bits(1) == cpython_generator.getrandbits(1)
        assert my_generator.gen_rand_bits(2) == cpython_generator.getrandbits(2)
        assert my_generator.gen_rand_bits(8) == cpython_generator.getrandbits(8)
        assert my_generator.gen_rand_bits(9) == cpython_generator.getrandbits(9)
        assert my_generator.gen_rand_bits(10) == cpython_generator.getrandbits(10)
        assert my_generator.gen_rand_bits(11) == cpython_generator.getrandbits(11)
        assert my_generator.gen_rand_bits(16) == cpython_generator.getrandbits(16)
        assert my_generator.gen_rand_bits(30) == cpython_generator.getrandbits(30)
        assert my_generator.gen_rand_bits(31) == cpython_generator.getrandbits(31)
        assert my_generator.gen_rand_bits(32) == cpython_generator.getrandbits(32)
        assert my_generator.gen_rand_bits(33) == cpython_generator.getrandbits(33)
        assert my_generator.gen_rand_bits(34) == cpython_generator.getrandbits(34)
        assert my_generator.gen_rand_bits(35) == cpython_generator.getrandbits(35)
        assert my_generator.gen_rand_bits(64) == cpython_generator.getrandbits(64)
        assert my_generator.gen_rand_bits(65) == cpython_generator.getrandbits(65)
        assert my_generator.gen_rand_bits(66) == cpython_generator.getrandbits(66)
        assert my_generator.gen_rand_bits(128) == cpython_generator.getrandbits(128)
        assert my_generator.gen_rand_bits(256) == cpython_generator.getrandbits(256)
        assert my_generator.gen_rand_bits(257) == cpython_generator.getrandbits(257)


def test_mersenne_twister_random_matches_random():
    """Verifies that the custom `random()` method matches `random.random()`."""
    seed = 0
    my_generator = MersenneTwisterGenerator(seed)
    cpython_generator = Random(seed)

    for _ in range(100):
        assert my_generator.random() == cpython_generator.random()


def test_getstate_setstate_reproducibility():
    """Verifies that `getstate` and `setstate` correctly save and restore state."""
    seed = 1357
    original_generator = MersenneTwisterGenerator(seed=seed)

    # Advance the generator a bit
    for _ in range(9876):
        original_generator.gen_rand_uint32()

    # Save the state
    state = original_generator.getstate()

    # Create a new generator and load the state
    restored_generator = MersenneTwisterGenerator(seed=2468)  # Different seed
    restored_generator.setstate(state)

    # Verify that the two generators produce the same sequence
    for _ in range(100):
        assert (
            original_generator.gen_rand_uint32() == restored_generator.gen_rand_uint32()
        )
        assert original_generator.random() == restored_generator.random()


def test_mersenne_twister_cracker_predicts_future_outputs():
    """Verifies that the cracker can predict future outputs of a generator."""
    target_seed = 123456789
    target_generator = Random(target_seed)

    # Consume some random numbers first to show that the predictor doesn't depend on the starting point of observation.
    [target_generator.getrandbits(32) for _ in range(1234)]
    observed_outputs = [target_generator.getrandbits(32) for _ in range(N)]

    # Instantiate the cracker and crack the state.
    cracked_generator = MersenneTwisterCracker.crack(observed_outputs)

    # Verify that the next 1000 outputs match the target's future outputs.
    for _ in range(1000):
        predicted_val = cracked_generator.gen_rand_uint32()
        actual_val = target_generator.getrandbits(32)
        assert predicted_val == actual_val


def test_mersenne_twister_cracker_predicts_future_outputs_by_z3():
    """Verifies that the cracker can predict future outputs of a generator."""
    target_seed = 987654321
    target_generator = Random(target_seed)

    # Consume some random numbers first to show that the predictor doesn't depend on the starting point of observation.
    [target_generator.getrandbits(32) for _ in range(1234)]
    observed_outputs = [target_generator.getrandbits(32) for _ in range(N)]

    # Instantiate the cracker and crack the state by z3 solver.
    cracked_generator = MersenneTwisterCracker.crack_by_z3(observed_outputs)

    # Verify that the next 1000 outputs match the target's future outputs.
    for _ in range(1000):
        predicted_val = cracked_generator.gen_rand_uint32()
        actual_val = target_generator.getrandbits(32)
        assert predicted_val == actual_val


@pytest.mark.repeat(10)
def test_mersenne_twister_cracker_with_live_data_bits32():
    """Verifies the cracker against live data from another Python process.

    This test provides strong evidence that the cracker works against a real-world
    Mersenne Twister implementation. It is repeated to test against different
    random seeds.
    """
    # Generate N + 1000 random numbers from an external Python script.
    # The first N numbers will be used for cracking, the next 1000 for verification.
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

    # Split the sequence into observed outputs and expected predictions.
    observed_outputs = full_sequence[:N]
    expected_predictions = full_sequence[N:]

    # Instantiate the cracker and crack the state.
    cracked_generator = MersenneTwisterCracker.crack(observed_outputs)

    # Verify that the next 100 outputs match the target's future outputs.
    for expected_val in expected_predictions:
        predicted_val = cracked_generator.gen_rand_uint32()
        assert predicted_val == expected_val


def test_cracker_from_random_predicts_future_outputs():
    """Verifies that the cracker can predict future outputs from observed floats."""
    target_seed = 445566
    num_to_observe = 800
    num_to_verify = 1000
    target_generator = MersenneTwisterGenerator(target_seed)

    # Collect enough float outputs from the target.
    observed_floats = [target_generator.random() for _ in range(num_to_observe)]

    # Instantiate the cracker and crack the state.
    cracked_generator = MersenneTwisterCracker.crack_from_random(observed_floats)
    expected_predictions = [target_generator.random() for _ in range(num_to_verify)]

    # Verify that the next 1000 outputs match the target's future outputs.
    for i, expected_val in enumerate(expected_predictions):
        predicted_val = cracked_generator.random()
        assert (
            predicted_val == expected_val
        ), f"Assertion failed: {predicted_val} != {expected_val} at index {i}"


def test_mersenne_twister_cracker_with_live_data_random():
    """Verifies the cracker against live data from another Python process.

    This test provides strong evidence that the cracker works against a real-world
    Mersenne Twister implementation.
    """
    # Generate 800 + 1000 random numbers from an external Python script.
    # The first 800 numbers will be used for cracking, the next 1000 for verification.
    num_to_observe = 800
    num_to_verify = 1000
    num_to_generate = num_to_observe + num_to_verify
    result = subprocess.run(
        [
            sys.executable,
            "sys_pseudo_rand_gen/py_random.py",
            str(num_to_generate),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    full_sequence = list(map(float, result.stdout.strip().split("\n")))

    # Split the sequence into observed outputs and expected predictions.
    observed_outputs = full_sequence[:num_to_observe]
    expected_predictions = full_sequence[num_to_observe:]

    # Instantiate the cracker and crack the state.
    cracked_generator = MersenneTwisterCracker.crack_from_random(observed_outputs)

    # Verify that the next 1000 outputs match the target's future outputs.
    for i, expected_val in enumerate(expected_predictions):
        predicted_val = cracked_generator.random()
        assert (
            predicted_val == expected_val
        ), f"Assertion failed: {predicted_val} != {expected_val} at index {i}"
