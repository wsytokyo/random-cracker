"""
A unified interface for cracking pseudo-random number generators (PRNGs).

This module provides tools to determine the internal state of a PRNG by observing
its output. Once the state is known, all future outputs can be predicted.

Supported PRNGs:
- V8's `Math.random()` (xorshift128+).
- CPython's `random` module (Mersenne Twister MT19937).
"""

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Generic, TypeVar

T = TypeVar("T")


class RngType(Enum):
    """Specifies the type of the pseudo-random number generator."""

    V8 = auto()
    """V8 Engine's `Math.random()`."""

    V8_LEGACY = auto()
    """V8 Engine's `Math.random()` (legacy)."""

    MT19937 = auto()
    """CPython's `random` module (MT19937)."""


class SolverStatus(Enum):
    """Represents the current status of a PRNG cracker."""

    SOLVING = auto()
    """Needs more values to determine the PRNG's state."""

    SOLVED = auto()
    """The PRNG's state has been successfully determined."""

    NOT_SOLVABLE = auto()
    """A solution cannot be found with the provided values."""

    # V8-specific statuses
    SOLVED_BEFORE_CACHE_REFILL = auto()
    """V8 only: A potential solution is found, but may be invalidated by a cache refill."""

    CACHE_REFILLED_WHILE_SOLVING = auto()
    """V8 only: A cache refill was detected, invalidating the current solving process."""


class NotSolvableError(RuntimeError):
    def __init__(self, message="The PRNG state is not solvable with the given values."):
        super().__init__(message)


class NotEnoughDataError(RuntimeError):
    def __init__(self, message="Not enough data to predict."):
        super().__init__(message)


class RandomCracker(ABC, Generic[T]):
    """An abstract base class defining the interface for a PRNG cracker."""

    rng_type: RngType
    """The type of the PRNG being cracked."""

    @staticmethod
    def create(rng_type: RngType) -> "RandomCracker":
        """Creates a `RandomCracker` instance for the specified `RngType`.

        This factory method performs a depth-first search through the subclass tree
        to find a cracker with a matching `rng_type`.
        """
        # Use an iterative DFS to find the correct subclass.
        classes_to_visit = list(RandomCracker.__subclasses__())
        while classes_to_visit:
            cls = classes_to_visit.pop()
            # If the class itself doesn't have the rng_type, it might be an abstract
            # base for other crackers (e.g., V8Cracker).
            if getattr(cls, "rng_type") == rng_type:
                return cls()
            classes_to_visit.extend(cls.__subclasses__())

        raise ValueError(f"No cracker available for the specified RNG type: {rng_type}")

    @property
    @abstractmethod
    def status(self) -> SolverStatus:
        """Returns the current status of the cracker."""

    @abstractmethod
    def predict_next(self) -> T:
        """
        Predicts the next value from the PRNG.

        This method should only be called when the status is `SOLVED` or
        `SOLVED_BEFORE_CACHE_REFILL`.

        Raises:
            NotSolvableError: If the state has not been solved.

        Returns:
            The predicted next value.
        """

    @abstractmethod
    def add_value(self, value: T) -> None:
        """
        Adds an observed value from the PRNG and attempts to solve for its internal state.

        Args:
            value: The observed value from the PRNG.

        Returns:
            None
        """
