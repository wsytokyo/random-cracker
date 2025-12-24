"""
A simple script to generate and print a sequence of pseudo-random floats.

This script is used by the test suite to generate live data from Python's
`random.random()` function.

Usage:
    python pseudo_random.py [count]

Arguments:
    count (int): The number of random floats to generate. Defaults to 10.
"""

import sys
from random import random


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    for _ in range(count):
        print(random())
