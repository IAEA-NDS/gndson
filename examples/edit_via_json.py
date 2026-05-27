"""
Demonstrate the edit-via-JSON workflow: load a GNDS XML file, modify it
through ordinary Python dict/list operations, save it, and verify the
change with FUDGE.

This script:
  1. Loads an input GNDS XML file (default: n_0125_1-H-1.xml from a
     local mirror of the GNDS reference corpus).
  2. Translates it to JSON via gndson.
  3. Scales the first reaction's first XYs1d cross-section block by a
     user-supplied factor (default 2.0).
  4. Tags the evaluated style with `library="demo-edited"` so the
     modification is visible in metadata too.
  5. Translates the modified JSON back to XML and writes it to disk.
  6. If FUDGE is importable, reads BOTH the original and the modified
     XML and prints the cross-section value at a reference energy to
     show the change took effect.

Run:
    python examples/edit_via_json.py [PATH/to/source.xml] \\
        [-o out.xml] [--factor 2.0] [--energy 1e6] [--skip-fudge]

The cross-section walk is deliberately specific to the GNDS layout used
by H-1 (and similar single-region files):
    reactionSuite / reactions / reaction[0] / crossSection / regions1d
    / function1ds / XYs1d[0] / values
If your input doesn't match, the script errors loudly with the path so
you can adapt it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


# Allow running directly from the repo without installing gndson.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gndson


DEFAULT_SOURCES = [
    Path("PATH/to/corpus/n_0125_1-H-1.xml"),
]


# ----- helpers -----


def find_default_source() -> Path:
    for p in DEFAULT_SOURCES:
        if p.is_file():
            return p
    sys.exit(
        "No default source XML found. Pass the path explicitly:\n"
        "  python examples/edit_via_json.py PATH/to/source.xml"
    )


def scale_first_xys_values(json_data: dict, factor: float) -> tuple[str, str]:
    """Find the first XYs1d in the first reaction's crossSection and scale
    its (E, σ) pairs in-place. Returns (before, after) preview strings."""
    try:
        rxn = json_data["reactionSuite"]["reactions"]["reaction"]
        # reaction may be scalar or list depending on count.
        rxn0 = rxn[0] if isinstance(rxn, list) else rxn
        xys = rxn0["crossSection"]["regions1d"]["function1ds"]["XYs1d"]
        xys0 = xys[0] if isinstance(xys, list) else xys
        raw_values = xys0["values"]
    except (KeyError, TypeError, IndexError) as e:
        raise SystemExit(
            "Could not locate the expected cross-section path "
            "reactionSuite/reactions/reaction[0]/crossSection/regions1d/"
            "function1ds/XYs1d[0]/values in the input. "
            f"Adapt the script's walk for this file. (caught: {e!r})"
        )
    tokens = raw_values.split()
    if len(tokens) % 2 != 0:
        raise SystemExit(
            f"values element has odd token count {len(tokens)}; expected (E, σ) pairs."
        )
    before = " ".join(tokens[:8]) + " ..."
    # Tokens at even positions are energies, odd positions are cross sections.
    scaled = []
    for i, tok in enumerate(tokens):
        if i % 2 == 1:
            scaled.append(repr(float(tok) * factor))
        else:
            scaled.append(tok)
    xys0["values"] = " ".join(scaled)
    after = " ".join(scaled[:8]) + " ..."
    return before, after


def tag_library(json_data: dict, new_library: str) -> None:
    """Rewrite the evaluated style's `library` attribute, leaving structure intact."""
    try:
        ev = json_data["reactionSuite"]["styles"]["evaluated"]
        ev["@library"] = new_library
    except (KeyError, TypeError):
        # Not fatal — informative only.
        pass


# ----- main -----


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("input", nargs="?", type=Path, default=None,
                    help="Source GNDS XML file (default: bundled H-1 corpus file).")
    ap.add_argument("-o", "--output", type=Path,
                    default=Path("/tmp/gndson_edited_h1.xml"),
                    help="Where to write the modified XML (default: /tmp/gndson_edited_h1.xml).")
    ap.add_argument("--factor", type=float, default=2.0,
                    help="Multiply the cross-section σ values by this factor (default 2.0).")
    ap.add_argument("--energy", type=float, default=1e6,
                    help="Reference energy (eV) at which to evaluate the cross section (default 1e6).")
    ap.add_argument("--skip-fudge", action="store_true",
                    help="Do not attempt the FUDGE verification step.")
    args = ap.parse_args(argv)

    src = args.input if args.input is not None else find_default_source()
    print(f"[source]   {src}", file=sys.stderr)

    # 1. Load via gndson.
    data = gndson.parse_xml_file(str(src))

    # 2. Edit in JSON-land.
    before, after = scale_first_xys_values(data, args.factor)
    tag_library(data, "demo-edited")
    print(f"[edit]     scaled cross section by ×{args.factor}", file=sys.stderr)
    print(f"           before: {before}", file=sys.stderr)
    print(f"           after:  {after}", file=sys.stderr)

    # 3. Write modified XML.
    gndson.write_xml_file(data, str(args.output))
    print(f"[output]   {args.output}", file=sys.stderr)

    # 4. Verify with FUDGE.
    if args.skip_fudge:
        return 0
    print("\n[FUDGE verification]", file=sys.stderr)
    try:
        from fudge import GNDS_file
    except ImportError:
        print("  FUDGE not available — skipping. "
              "Re-run with a Python that has FUDGE installed to enable the check.",
              file=sys.stderr)
        return 0

    def eval_first_xs(path: Path) -> float:
        rs = GNDS_file.read(str(path))
        cs = rs.reactions[0].crossSection.evaluated
        return cs.evaluate(args.energy)

    original_xs = eval_first_xs(src)
    edited_xs = eval_first_xs(args.output)
    ratio = edited_xs / original_xs if original_xs else float("nan")
    print(f"  original σ({args.energy:g} eV) = {original_xs:g} b", file=sys.stderr)
    print(f"  edited   σ({args.energy:g} eV) = {edited_xs:g} b", file=sys.stderr)
    print(f"  ratio (expected {args.factor:g}):  {ratio:g}", file=sys.stderr)

    # Sanity check: ratio should be close to the requested factor.
    if abs(ratio - args.factor) > 1e-6 * max(1.0, args.factor):
        print(f"  WARNING: ratio differs from expected factor by more than 1e-6",
              file=sys.stderr)
        return 1
    print(f"  OK: edit reflected in FUDGE's view", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
