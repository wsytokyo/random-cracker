import sys
import argparse
from crackers.random_cracker import (
    RandomCracker,
    RngType,
    NotEnoughDataError,
    NotSolvableError,
    SolverStatus,
)


def main():
    # Use enum names for choices
    rngtype_choices = [e.name for e in RngType]
    rngtype_help = ", ".join(rngtype_choices)

    parser = argparse.ArgumentParser(
        description="Crack PRNGs and predict future outputs."
    )
    parser.add_argument(
        "-t",
        "--type",
        required=True,
        choices=rngtype_choices,
        help="Type of cracker: " + rngtype_help,
    )
    parser.add_argument(
        "-p",
        "--predict",
        type=int,
        default=10,
        help="Number of predictions to output (default: 10)",
    )
    parser.add_argument(
        "-m",
        "--multiplier",
        type=int,
        default=None,
        help="Multiplier for V8_INT cracker (optional)",
    )
    try:
        args = parser.parse_args()
    except SystemExit:
        parser.print_help()
        sys.exit(1)

    # Map string to RngType by name
    try:
        rng_type = RngType[args.type]
    except Exception:
        print(f"Invalid RNG type: {args.type}", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    # Create cracker
    kwargs = {}
    if rng_type == getattr(RngType, "V8_INT", None) and args.multiplier is not None:
        kwargs["multiplier"] = args.multiplier
    cracker = RandomCracker.create(rng_type, **kwargs)

    # Read and feed observed values from stdin, checking status after each
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                if rng_type == RngType.V8 or rng_type == RngType.V8_LEGACY:
                    val = float(line)
                else:
                    val = int(line)
            except ValueError:
                print(f"Invalid input: {line}", file=sys.stderr)
                parser.print_help()
                sys.exit(1)
            cracker.add_value(val)
            if cracker.status == SolverStatus.NOT_SOLVABLE:
                raise NotSolvableError()
            if (
                cracker.status == SolverStatus.SOLVED
                or cracker.status == SolverStatus.SOLVED_BEFORE_CACHE_REFILL
            ):
                break
    except NotSolvableError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    # Predict and output
    try:
        for _ in range(args.predict):
            print(cracker.predict_next())
    except NotEnoughDataError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(3)
    except NotSolvableError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
