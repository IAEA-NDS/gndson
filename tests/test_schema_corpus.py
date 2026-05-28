"""
Corpus round-trip test for schema-layer transformations.

For each XML file in the corpus, this driver checks the schema-layer
round-trip property:

    canonical = parse_xml(file)
    canonical == pipeline.inverse(pipeline.forward(canonical))

A pass means: applying the pipeline's forward and then its inverse
returns the canonical JSON bit-for-bit. The bottom-layer XML round-trip
(parser ↔ serializer) is verified separately in
`tests/test_roundtrip_corpus.py`; this driver layers the schema-pipeline
check on top of an already-trusted base.

Usage (pytest):
    pytest --gnds-corpus /path/to/corpus

Usage (script):
    python tests/test_schema_corpus.py /path/to/corpus
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# Allow running as a standalone script (not just under pytest).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import gndson
from gndson.schema.base import Pipeline
from gndson.schema.pipelines import FUZZY_PIPELINES, PIPELINES


# Named pipelines exercised by the corpus driver. We test every pipeline
# declared in `gndson.schema.pipelines` so the CLI and the corpus driver
# stay in lock-step — anything a user can name on `--pipeline` is verified
# to round-trip across the corpus.
PIPELINES_UNDER_TEST = {
    name: pipeline for name, pipeline in PIPELINES.items()
    # Skip the no-op identity pipeline (its round-trip check is trivial).
    if len(pipeline.transformations) > 0
}


def list_corpus_files(root: Path):
    files = sorted(root.glob("*.xml"))
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
        files += sorted(sub.glob("*.xml"))
    return files


def check_canonical(canonical: dict, pipeline: Pipeline, fuzzy_tags=None):
    """Round-trip check on a pre-parsed canonical dict.

    If `fuzzy_tags` is provided (a set of tag names), the comparison
    whitespace-normalises the listed tags in both the original canonical
    and the round-trip result before comparing — for pipelines that are
    bijective at the GNDS-spec level but not at the canonical-form byte
    level (see FUZZY_PIPELINES in gndson.schema.pipelines).
    """
    try:
        transformed = pipeline.forward(canonical)
    except Exception as e:
        return False, f"forward: {type(e).__name__}: {e}"
    try:
        restored = pipeline.inverse(transformed)
    except Exception as e:
        return False, f"inverse: {type(e).__name__}: {e}"
    if fuzzy_tags is not None:
        if _normalise_ws(canonical, fuzzy_tags) != _normalise_ws(restored, fuzzy_tags):
            return False, "mismatch (fuzzy)"
    else:
        if restored != canonical:
            return False, "mismatch"
    return True, ""


def _normalise_ws(data, tags):
    """Return a deep copy of `data` with whitespace-normalised text bodies
    for elements whose tag is in `tags`. Handles three shapes:

      bare-string:  {values: "  1\\n  2\\n  3  "} -> {values: "1 2 3"}
      object form:  {values: {"@a": "x", "_text": "1\\n 2"}}
                       -> {values: {"@a": "x", "_text": "1 2"}}
      list of either: each item gets the appropriate normalisation.

    Tag context is tracked so we can normalise `_text` only when its
    enclosing dict is itself a tokenised element.
    """
    from copy import deepcopy
    out = deepcopy(data)
    _walk_normalise(out, tags, tag=None)
    return out


def _walk_normalise(data, tags, tag=None):
    if isinstance(data, dict):
        # If this node IS a tokenised element in object form, normalise its
        # `_text` value.
        if tag in tags:
            text = data.get("_text")
            if isinstance(text, str):
                data["_text"] = " ".join(text.split())
        # Process tokenised children of this node.
        for k, v in list(data.items()):
            if k.startswith("@") or k.startswith("_"):
                continue
            if k in tags:
                if isinstance(v, str):
                    data[k] = " ".join(v.split())
                elif isinstance(v, list):
                    new_items = []
                    for item in v:
                        if isinstance(item, str):
                            new_items.append(" ".join(item.split()))
                        else:
                            new_items.append(item)
                    data[k] = new_items
            # Recurse with tag context.
            child = data[k]
            if isinstance(child, dict):
                _walk_normalise(child, tags, tag=k)
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, dict):
                        _walk_normalise(item, tags, tag=k)


def summarise(files, pipelines):
    """Run every pipeline against every file. Each XML file is parsed ONCE
    and its canonical dict reused across all pipelines, avoiding O(files ×
    pipelines) parse cost. Returns a list of (pipeline_name, ok_count,
    failures) tuples in the order the pipelines were declared."""
    results = {name: {"ok": 0, "failures": []} for name in pipelines}
    for f in files:
        try:
            canonical = gndson.parse_xml_file(str(f))
        except Exception as e:
            reason = f"parse: {type(e).__name__}: {e}"
            for name in pipelines:
                results[name]["failures"].append((f.name, reason))
            continue
        for name, pipeline in pipelines.items():
            fuzzy = FUZZY_PIPELINES.get(name)
            ok, reason = check_canonical(canonical, pipeline, fuzzy_tags=fuzzy)
            if ok:
                results[name]["ok"] += 1
            else:
                results[name]["failures"].append((f.name, reason))
    return [
        (name, info["ok"], info["failures"])
        for name, info in results.items()
    ]


def print_summary(name, ok, failures, total, stream=sys.stdout):
    pct = ok * 100 / total if total else 0.0
    print(f"\n[{name}] {ok}/{total} round-trip OK ({pct:.1f}%)", file=stream)
    if failures:
        buckets = Counter(r.split(":")[0] for _, r in failures)
        print(f"  Failure breakdown:", file=stream)
        for reason, count in buckets.most_common():
            print(f"    {count:>4}  {reason}", file=stream)


# ----- pytest entry -----


def test_schema_corpus_round_trip(request):
    corpus = request.config.getoption("--gnds-corpus")
    if corpus is None:
        pytest.skip("no --gnds-corpus PATH provided")
    root = Path(corpus)
    if not root.is_dir():
        pytest.fail(f"--gnds-corpus path is not a directory: {root}")
    files = list_corpus_files(root)
    if not files:
        pytest.skip(f"no .xml files found under {root}")

    for pipeline_name, ok, failures in summarise(files, PIPELINES_UNDER_TEST):
        print_summary(pipeline_name, ok, failures, len(files))


# ----- script entry -----


def main():
    ap = argparse.ArgumentParser(
        description="Schema-layer round-trip test over a corpus of GNDS XML files.",
    )
    ap.add_argument("corpus", type=Path,
                    help="Directory of GNDS XML files (one subdirectory deep is scanned too).")
    ap.add_argument("--list-failures", type=int, default=10,
                    help="Maximum individual failures to print per pipeline (default: 10).")
    args = ap.parse_args()
    if not args.corpus.is_dir():
        print(f"Not a directory: {args.corpus}", file=sys.stderr)
        sys.exit(2)
    files = list_corpus_files(args.corpus)
    if not files:
        print(f"No .xml files under {args.corpus}", file=sys.stderr)
        sys.exit(2)

    overall_ok = True
    for pipeline_name, ok, failures in summarise(files, PIPELINES_UNDER_TEST):
        for name, reason in failures[: args.list_failures]:
            print(f"FAIL [{pipeline_name}] {name}: {reason}")
        if len(failures) > args.list_failures:
            print(f"... and {len(failures) - args.list_failures} more failures")
        print_summary(pipeline_name, ok, failures, len(files))
        if ok != len(files):
            overall_ok = False

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
