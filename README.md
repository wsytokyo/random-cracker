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

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS
pip install -r requirements.txt
```

2. Run the test suite:

```bash
pytest
```

## Project Structure

- `v8_random_cracker.py`: Main implementation for V8 random number cracker
- `mersenne_twister_cracker.py`: Mersenne Twister cracker implementation
- `tests/`: Test suite for cracker implementations
- `sys_pseudo_rand_gen/`: System pseudo-random generator utilities

## License

This project is licensed under the terms of the license specified in the LICENSE file.
