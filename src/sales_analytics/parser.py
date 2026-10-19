import argparse
from datetime import date
from pathlib import Path
from .config import DEFAULT_REPORTS_DIR


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments and validate the requested date range."""
    parser = argparse.ArgumentParser(
        description="Run the sales analytics pipeline."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help="Directory where CSV reports will be saved.",
    )
    parser.add_argument(
        "--from-date",
        type=date.fromisoformat,
        default=None,
        metavar="YYYY-MM-DD",
        help="Include orders from this date onwards.",
    )
    parser.add_argument(
        "--to-date",
        type=date.fromisoformat,
        default=None,
        metavar="YYYY-MM-DD",
        help="Include orders up to and including this date.",
    )
    args = parser.parse_args()

    if (
            args.from_date is not None
            and args.to_date is not None
            and args.from_date > args.to_date
    ):
        parser.error("--from-date must be earlier than or equal to --to-date")

    return args