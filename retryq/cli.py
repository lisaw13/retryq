import argparse
import json
import sys

from .policy import PolicyError, RetryPolicy


def read_source(source):
    if source == "-":
        return sys.stdin.read()
    with open(source, "r") as f:
        return f.read()


def format_seconds(value):
    return f"{value:.2f}s"


def build_parser():
    parser = argparse.ArgumentParser(
        prog="retryq",
        description="Show the backoff schedule a retry policy produces.",
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="-",
        help="path to a JSON policy file, or - to read from stdin (default: -)",
    )
    parser.add_argument(
        "--attempt",
        type=int,
        metavar="N",
        help="only report the delay bounds for attempt N, instead of the full schedule",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        text = read_source(args.source)
    except OSError as exc:
        print(f"retryq: could not read {args.source}: {exc}", file=sys.stderr)
        return 1

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"retryq: invalid JSON: {exc}", file=sys.stderr)
        return 1

    try:
        policy = RetryPolicy.from_dict(data)
    except PolicyError as exc:
        print(f"retryq: invalid policy: {exc}", file=sys.stderr)
        return 1

    if args.attempt is not None:
        return _report_single_attempt(policy, args.attempt)

    _print_schedule(policy)
    return 0


def _report_single_attempt(policy, attempt):
    if not policy.will_retry(attempt):
        print(f"attempt {attempt}: no retry (max_attempts is {policy.max_attempts})")
        return 0
    lo, hi = policy.delay_bounds(attempt)
    if lo == hi:
        print(f"attempt {attempt}: delay {format_seconds(lo)}")
    else:
        print(f"attempt {attempt}: delay between {format_seconds(lo)} and {format_seconds(hi)}")
    return 0


def _print_schedule(policy):
    header = (
        f"{'attempt':>7}  {'delay (min)':>12}  {'delay (max)':>12}  "
        f"{'elapsed (min)':>14}  {'elapsed (max)':>14}"
    )
    print(header)
    print("-" * len(header))
    for attempt, lo, hi, cum_lo, cum_hi in policy.schedule():
        print(
            f"{attempt:>7}  {format_seconds(lo):>12}  {format_seconds(hi):>12}  "
            f"{format_seconds(cum_lo):>14}  {format_seconds(cum_hi):>14}"
        )


if __name__ == "__main__":
    sys.exit(main())
