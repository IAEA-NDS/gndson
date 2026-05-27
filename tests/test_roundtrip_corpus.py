"""
Corpus round-trip test driver.

Walks a user-supplied directory of GNDS XML files. For each file:
  1. parse the ORIGINAL XML into faithful trees (lossless, two flavours)
  2. translate ORIGINAL XML -> JSON via gndson.parse
  3. untranslate JSON -> re-XML via gndson.to_xml_string
  4. parse the RE-XML into faithful trees (the same two flavours)
  5. compare each pair, at two levels:
       - spec-equivalence (§9): ignores self-closing-vs-pair, attribute order,
         attribute quote, inter-tag whitespace, minimal entity escaping.
       - byte-form-strict: as above, but the self-closing-vs-pair distinction
         IS preserved (verifies that _nocollapse round-trips correctly).

Per spec §9 the round-trip property is the spec-equivalence one. The
byte-form-strict number is a stricter additional metric: every byte-form
pass count <= the corresponding spec-equivalence count. If they differ,
_nocollapse coverage is the suspect.

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

from xml_compare import parse_faithful, diff_summary


# ----- core driver -----


def list_corpus_files(corpus_root: Path):
    """Return all *.xml files under `corpus_root`, including one subdirectory deep
    (the GNDS corpus places covariance files in a sibling `Covariances/` folder)."""
    files = sorted(corpus_root.glob("*.xml"))
    for sub in sorted(p for p in corpus_root.iterdir() if p.is_dir()):
        files += sorted(sub.glob("*.xml"))
    return files


def round_trip_one(path: Path):
    """Run the round-trip on one file at two checking levels.

    Returns ``(spec_ok, strict_ok, reason)``:
      - ``spec_ok``: True iff the round-trip is XML-equivalent per spec §9.
      - ``strict_ok``: True iff additionally the self-closing-vs-pair form
        was preserved (which is what ``_nocollapse`` is for).
      - ``reason``: empty if both pass; otherwise the first failure's reason.

    ``strict_ok`` is meaningful only when ``spec_ok`` is True; if spec-equivalence
    fails, strict_ok is reported as False too.
    """
    try:
        original_bytes = path.read_bytes()
    except Exception as e:
        return False, False, f"read: {type(e).__name__}: {e}"
    try:
        json_1 = gndson.parse_xml_bytes(original_bytes)
    except gndson.GndsonError as e:
        return False, False, f"translate: {type(e).__name__}: {e}"
    except Exception as e:
        return False, False, f"translate-unexpected: {type(e).__name__}: {e}"
    try:
        xml_text = gndson.to_xml_string(json_1)
    except gndson.GndsonError as e:
        return False, False, f"untranslate: {type(e).__name__}: {e}"
    except Exception as e:
        return False, False, f"untranslate-unexpected: {type(e).__name__}: {e}"
    re_bytes = xml_text.encode("utf-8")

    # Level 1: spec-equivalence.
    try:
        spec_a = parse_faithful(original_bytes)
        spec_b = parse_faithful(re_bytes)
    except Exception as e:
        return False, False, f"faithful-parse: {type(e).__name__}: {e}"
    if spec_a != spec_b:
        return False, False, "spec-diff: " + diff_summary(spec_a, spec_b)

    # Level 2: byte-form-strict (only run if spec-equivalence passed).
    strict_a = parse_faithful(original_bytes, strict_form=True)
    strict_b = parse_faithful(re_bytes, strict_form=True)
    if strict_a != strict_b:
        return True, False, "form-diff: " + diff_summary(strict_a, strict_b)

    return True, True, ""


def summarise(files):
    spec_ok_count = 0
    strict_ok_count = 0
    failures = []  # list of (name, reason). Either-level failure recorded once.
    for f in files:
        spec_ok, strict_ok, reason = round_trip_one(f)
        if spec_ok:
            spec_ok_count += 1
        if strict_ok:
            strict_ok_count += 1
        if not (spec_ok and strict_ok):
            failures.append((f.name, reason))
    return spec_ok_count, strict_ok_count, failures


def print_summary(spec_ok, strict_ok, failures, total, stream=sys.stdout):
    spec_pct = spec_ok * 100 / total if total else 0.0
    strict_pct = strict_ok * 100 / total if total else 0.0
    print(file=stream)
    print(f"Spec-equivalence round-trip (§9): {spec_ok}/{total} ({spec_pct:.1f}%)", file=stream)
    print(f"Byte-form-strict round-trip:      {strict_ok}/{total} ({strict_pct:.1f}%)", file=stream)
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
    spec_ok, strict_ok, failures = summarise(files)
    print_summary(spec_ok, strict_ok, failures, len(files))


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

    spec_ok, strict_ok, failures = summarise(files)
    for name, reason in failures[: args.list_failures]:
        print(f"FAIL {name}: {reason}")
    if len(failures) > args.list_failures:
        print(f"... and {len(failures) - args.list_failures} more failures")
    print_summary(spec_ok, strict_ok, failures, len(files))


if __name__ == "__main__":
    main()
