"""
A simple script to generate and print a sequence of pseudo-random integers.

This script is used by the test suite to generate integer data from Python's
`random` module.

Usage:
    python pseudo_random_int16.py [count]

Arguments:
    count (int): The number of random integers to generate. Defaults to 10.
"""

import sys
from random import randrange

MAX = 2**16


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    for _ in range(count):
        print(randrange(MAX))
