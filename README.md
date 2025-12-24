# Random Number Cracker

A collection of tools for analyzing and cracking various random number generators, including:

- V8 random number generator (JavaScript)
- Mersenne Twister random number generator (Python)

## Features

- Implementation of random number cracker algorithms
- Test suite for verifying cracker effectiveness
- Support for multiple random number generator types
- Live data testing capabilities

## Usage

### Command-line Tool

You can use the CLI tool to predict future outputs of supported PRNGs.

```bash
python3 main.py -t TYPE [-p NUM_PREDICTIONS] [--multiplier MULTIPLIER] < input_values.txt
```

- `-t, --type`: Type of cracker. One of: V8, V8_INT, V8_LEGACY, MT19937 (required)
- `-p, --predict`: Number of predictions to output (default: 10)
- `-m, --multiplier`: Multiplier for V8_INT cracker (optional)
- Input values: Provide observed PRNG outputs via stdin (one value per line)

**Example:**

```bash
python3 main.py -t V8 < examples/observed_values.txt
python3 main.py -t MT19937 -p 20 < examples/mt_outputs.txt
python3 main.py -t V8_INT --multiplier 1234567890123456 < examples/v8_int_outputs.txt
```

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Unix/macOS
pip install -r requirements.txt
```

2. Run the test suite:

```bash
pytest
```

## Project Structure

- `main.py`: Command-line tool for cracking and predicting PRNG outputs
- `crackers/`: Package containing all cracker implementations
  - `random_cracker.py`: Unified interface and base classes for crackers
  - `v8_cracker.py`: V8 random number cracker (modern)
  - `v8_cracker_legacy.py`: V8 random number cracker (legacy)
  - `mt19937_cracker.py`: Mersenne Twister cracker implementation
- `tests/`: Test suite for cracker implementations
- `sys_pseudo_rand_gen/`: Utilities for generating system PRNG outputs for testing

## License

This project is licensed under the terms of the license specified in the LICENSE file.
