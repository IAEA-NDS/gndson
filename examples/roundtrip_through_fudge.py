"""
Round-trip identity through FUDGE: confirm that a gndson XML -> JSON -> XML
round trip preserves the GNDS data so faithfully that FUDGE sees no change.

For each input file the script:
  1. Reads the ORIGINAL XML with FUDGE; captures FUDGE's canonical
     toXML() output (call it A).
  2. Runs the original XML through gndson (XML -> JSON -> XML) into a
     temp file.
  3. Reads the ROUND-TRIPPED XML with FUDGE; captures its toXML() (call
     it B).
  4. Compares A and B at two levels:
       - structural: A and B parse to the same faithful XML tree
         (ignoring inter-tag whitespace, attribute order, self-closing
         vs pair form — i.e. all of spec §9's allowed differences).
       - data: cross-section values evaluated at a set of reference
         energies must match exactly.

If both checks pass for a file, gndson's round trip is "identity through
FUDGE" — FUDGE cannot tell the original from the round-tripped version.

Run:
    python examples/roundtrip_through_fudge.py             # default file
    python examples/roundtrip_through_fudge.py FILE...     # specific files
    python examples/roundtrip_through_fudge.py --energies 0.025 1 1e3 1e6

Requires FUDGE to be importable.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


# Allow running directly from the repo without installing gndson.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gndson
from gndson._compare import parse_faithful, diff_summary


DEFAULT_INPUTS = [
    Path("PATH/to/corpus/n_0125_1-H-1.xml"),
]


# ----- the round-trip identity check -----


def check_one(path: Path, energies, verbose: bool = True) -> bool:
    from fudge import GNDS_file

    if verbose:
        print(f"\n[file] {path.name}", file=sys.stderr)

    # 1. Original through FUDGE.
    rs_a = GNDS_file.read(str(path))
    fudge_a = rs_a.toXML()

    # 2. Round-trip via gndson.
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        rt_path = Path(tmp.name)
    try:
        gndson.write_xml_file(gndson.parse_xml_file(str(path)), str(rt_path))

        # 3. Round-trip output through FUDGE.
        rs_b = GNDS_file.read(str(rt_path))
        fudge_b = rs_b.toXML()
    finally:
        rt_path.unlink(missing_ok=True)

    # 4a. Structural check: faithful-tree equality of FUDGE's two toXML outputs.
    tree_a = parse_faithful(fudge_a.encode("utf-8"))
    tree_b = parse_faithful(fudge_b.encode("utf-8"))
    if tree_a != tree_b:
        print(f"  STRUCTURAL FAIL: {diff_summary(tree_a, tree_b)}", file=sys.stderr)
        return False
    if verbose:
        print(f"  structural identity: OK "
              f"({len(fudge_a):,} chars / {len(fudge_b):,} chars from fudge.toXML)",
              file=sys.stderr)

    # 4b. Data check: cross sections evaluated at the sample energies.
    # Only meaningful for ReactionSuite files; CovarianceSuite and other
    # GNDS document types don't carry directly-evaluatable cross sections,
    # so for them the structural check is the only check we can do.
    if not hasattr(rs_a, "reactions"):
        if verbose:
            print(f"  data identity: SKIPPED ({type(rs_a).__name__} has no "
                  "directly-evaluatable cross sections; structural-only)",
                  file=sys.stderr)
        return True

    # If a cross section type is not directly evaluatable on the ORIGINAL
    # (e.g. ResonancesWithBackground without reconstruction), we don't
    # treat it as a round-trip failure — it's a fudge-API limitation that
    # would manifest identically on both sides. Failure means: original
    # was evaluatable, round-trip differs.
    data_ok = True
    compared = 0
    skipped = 0
    for r_idx, (ra, rb) in enumerate(zip(rs_a.reactions, rs_b.reactions)):
        cs_a = ra.crossSection.evaluated
        cs_b = rb.crossSection.evaluated
        for E in energies:
            try:
                va = cs_a.evaluate(E)
            except Exception:
                skipped += 1
                continue
            try:
                vb = cs_b.evaluate(E)
            except Exception as e:
                print(f"  DATA FAIL: reaction {r_idx} ({ra.label!r}) "
                      f"original evaluatable at E={E:g} but round-trip is not: "
                      f"{type(e).__name__}: {e}", file=sys.stderr)
                data_ok = False
                continue
            if va != vb:
                print(f"  DATA FAIL: reaction {r_idx} ({ra.label!r}) "
                      f"σ({E:g}) = {va!r} vs {vb!r}", file=sys.stderr)
                data_ok = False
            else:
                compared += 1
    if data_ok and verbose:
        skip_note = f", {skipped} not directly evaluatable" if skipped else ""
        print(f"  data identity: OK ({compared} cross-section evaluations match"
              f"{skip_note})", file=sys.stderr)

    return data_ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("files", nargs="*", type=Path,
                    help="GNDS XML files to check (default: bundled H-1 corpus file).")
    ap.add_argument("--energies", type=float, nargs="+",
                    default=[0.025, 1.0, 1e3, 1e6, 1e7],
                    help="Energies (eV) at which to compare cross sections.")
    args = ap.parse_args(argv)

    try:
        import fudge  # noqa: F401
    except ImportError:
        print("This example requires FUDGE. Re-run with a Python that has FUDGE installed.",
              file=sys.stderr)
        return 2

    files = args.files if args.files else [p for p in DEFAULT_INPUTS if p.is_file()]
    if not files:
        sys.exit("No input files given and no default file found. Pass paths explicitly.")

    ok_count = 0
    crashed = 0
    for f in files:
        try:
            if check_one(f, args.energies):
                ok_count += 1
        except Exception as e:
            # Don't let one bad file kill the batch.
            crashed += 1
            print(f"  CRASH: {type(e).__name__}: {e}", file=sys.stderr)

    crash_note = f", {crashed} crashed" if crashed else ""
    print(f"\n[summary] {ok_count}/{len(files)} files round-trip identity-equal "
          f"through FUDGE{crash_note}", file=sys.stderr)
    return 0 if ok_count == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
