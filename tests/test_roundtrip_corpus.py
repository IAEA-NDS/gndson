"""
Corpus round-trip test driver.

Walks a user-supplied directory of GNDS XML files and for each file:
  1. parse XML        -> JSON_1
  2. serialize JSON_1 -> re-XML
  3. parse re-XML     -> JSON_2
  4. assert JSON_1 == JSON_2

NB: JSON stability is NECESSARY but not SUFFICIENT for true round-trip.
If the parser is currently lossy for some XML feature (e.g. drops comments
in an early iteration), both parses agree on the lossy form and the test
passes deceptively. A stricter XML-equivalence check belongs to a later
iteration. See spec §9.

Usage (pytest):
    pytest --gnds-corpus /path/to/corpus

Usage (script):
    python tests/test_roundtrip_corpus.py /path/to/corpus
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

# Allow running as a standalone script (not just under pytest).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import gndson


# ----- core driver -----


def list_corpus_files(corpus_root: Path):
    """Return all *.xml files under `corpus_root`, including one subdirectory deep
    (the GNDS corpus places covariance files in a sibling `Covariances/` folder)."""
    files = sorted(corpus_root.glob("*.xml"))
    for sub in sorted(p for p in corpus_root.iterdir() if p.is_dir()):
        files += sorted(sub.glob("*.xml"))
    return files


def round_trip_one(path: Path):
    """Run the round-trip on one file. Returns (ok: bool, reason: str)."""
    try:
        json_1 = gndson.parse_xml_file(str(path))
    except gndson.GndsonError as e:
        return False, f"parse: {type(e).__name__}: {e}"
    except Exception as e:
        return False, f"parse-unexpected: {type(e).__name__}: {e}"
    try:
        xml_text = gndson.to_xml_string(json_1)
    except gndson.GndsonError as e:
        return False, f"serialize: {type(e).__name__}: {e}"
    except Exception as e:
        return False, f"serialize-unexpected: {type(e).__name__}: {e}"
    try:
        json_2 = gndson.parse_xml_bytes(xml_text.encode("utf-8"))
    except gndson.GndsonError as e:
        return False, f"reparse: {type(e).__name__}: {e}"
    except Exception as e:
        return False, f"reparse-unexpected: {type(e).__name__}: {e}"
    if json_1 != json_2:
        return False, "mismatch"
    return True, ""


def summarise(files):
    ok_count = 0
    failures = []
    for f in files:
        ok, reason = round_trip_one(f)
        if ok:
            ok_count += 1
        else:
            failures.append((f.name, reason))
    return ok_count, failures


def print_summary(ok_count, failures, total, stream=sys.stdout):
    pct = ok_count * 100 / total if total else 0.0
    print(f"\nRound-trip pass rate: {ok_count}/{total} ({pct:.1f}%)", file=stream)
    if failures:
        buckets = Counter(r.split(":")[0] for _, r in failures)
        print("Failure breakdown:", file=stream)
        for reason, count in buckets.most_common():
            print(f"  {count:>4}  {reason}", file=stream)


# ----- pytest entry -----


def test_corpus_round_trip(request):
    """JSON-stability round-trip over a user-supplied corpus directory.

    Run with::

        pytest --gnds-corpus /path/to/corpus

    Asserts only that the driver ran. The rolling pass rate is printed
    (use ``-s`` to see it during a green run) and is the development signal.
    """
    corpus = request.config.getoption("--gnds-corpus")
    if corpus is None:
        pytest.skip("no --gnds-corpus PATH provided")
    corpus_root = Path(corpus)
    if not corpus_root.is_dir():
        pytest.fail(f"--gnds-corpus path is not a directory: {corpus_root}")
    files = list_corpus_files(corpus_root)
    if not files:
        pytest.skip(f"no .xml files found under {corpus_root}")
    ok_count, failures = summarise(files)
    print_summary(ok_count, failures, len(files))


# ----- script entry -----


def main():
    ap = argparse.ArgumentParser(
        description="Run the gndson round-trip test over a directory of GNDS XML files."
    )
    ap.add_argument(
        "corpus",
        type=Path,
        help="Path to a directory containing GNDS XML files (one subdirectory deep is also scanned).",
    )
    ap.add_argument(
        "--list-failures",
        type=int,
        default=20,
        help="Maximum number of individual failures to print (default: 20).",
    )
    args = ap.parse_args()

    if not args.corpus.is_dir():
        print(f"Not a directory: {args.corpus}", file=sys.stderr)
        sys.exit(2)
    files = list_corpus_files(args.corpus)
    if not files:
        print(f"No .xml files found under {args.corpus}", file=sys.stderr)
        sys.exit(2)

    ok_count, failures = summarise(files)
    for name, reason in failures[: args.list_failures]:
        print(f"FAIL {name}: {reason}")
    if len(failures) > args.list_failures:
        print(f"... and {len(failures) - args.list_failures} more failures")
    print_summary(ok_count, failures, len(files))


if __name__ == "__main__":
    main()
