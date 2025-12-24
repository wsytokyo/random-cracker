# Random Number Cracker

Random Number Cracker is a Z3-powered toolkit for reconstructing the internal
state of popular pseudo-random number generators (PRNGs) from their observed
outputs. It ships with ready-to-run crackers for the V8 JavaScript engine
(modern, legacy, and integer-multiplier variants) as well as CPython's
Mersenne Twister, plus a CLI that streams predictions once the solver locks
onto the hidden state.

## Features

- **Multi-PRNG coverage** – Crack V8 (`Math.random()`) modern, legacy, and
  integer-multiplier modes alongside CPython's MT19937 (`random.getrandbits`).
- **Constraint-solver pipeline** – Incrementally feed observed outputs into a
  solver that detects cache refills, recovers internal state, and emits
  deterministic predictions.
- **Command-line workflow** – Stream PRNG samples via stdin and print future
  outputs with flexible prediction counts and V8_INT multipliers.
- **Live data harnesses** – Reproduce real engine behavior using the Node.js
  and Python helpers under `sys_pseudo_rand_gen/` for end-to-end validation.
- **Comprehensive pytest suite** – Deterministic and live-data tests ensure the
  crackers stay accurate across engines and seeds.

## Installation

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Unix/macOS
pip install -r requirements.txt
```

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

## Testing

Run the pytest suite to verify functionality:

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
