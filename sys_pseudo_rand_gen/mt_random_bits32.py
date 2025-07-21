"""
A simple script to generate and print a sequence of pseudo-random 32-bit integers.

This script is used by the test suite to generate live data from Python's
`random.Random` class.

Usage:
    python pseudo_random_bits32.py [count]

Arguments:
    count (int): The number of random 32-bit integers to generate. Defaults to 10.
"""

import sys
from random import Random


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    rnd = Random()
    for _ in range(count):
        print(rnd.getrandbits(32))
