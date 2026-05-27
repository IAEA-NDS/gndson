"""Pytest conftest: import path + corpus option."""

import sys
from pathlib import Path

# Make the in-tree `gndson` package importable without `pip install -e .`.
sys.path.insert(0, str(Path(__file__).parent))


def pytest_addoption(parser):
    parser.addoption(
        "--gnds-corpus",
        action="store",
        default=None,
        metavar="PATH",
        help=(
            "Path to a directory of GNDS XML files used by the corpus "
            "round-trip test. If omitted, that test is skipped."
        ),
    )
