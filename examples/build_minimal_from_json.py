"""
Hand-author a minimal GNDS reactionSuite as a Python dict (the canonical
gndson JSON form), translate it to XML, and verify the result with FUDGE.

This demonstrates that the gndson JSON encoding is structured enough that
you can author GNDS data directly in Python with little ceremony, and that
the XML produced is consumed correctly by an existing GNDS library.

The example builds a one-reaction file: neutron + H-1 elastic scattering
(MT=2) with a flat 20.4 b cross section across the resolved region — a
deliberately tiny but spec-conformant document.

Run:
    python examples/build_minimal_from_json.py            # print XML to stdout
    python examples/build_minimal_from_json.py -o out.xml # also write to file

The FUDGE check is optional; if `fudge` cannot be imported, the script
still prints the generated XML. To enable the check, run the script with
a Python that has FUDGE installed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


# Allow running directly from the repo without installing gndson.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gndson


# ----- small helpers to keep the GNDS dict readable -----


def axes(*labels_units):
    """Build an `axes` block from (label, unit) pairs, indexed top-down."""
    n = len(labels_units)
    return {"axis": [
        {"@index": str(n - 1 - i), "@label": label, "@unit": unit}
        for i, (label, unit) in enumerate(labels_units)
    ]}


def constant1d(value, *, label="eval", domain=("1e-5", "2e7"),
               quantity_label="Q", unit="eV"):
    return {"constant1d": {
        "@label": label, "@value": str(value),
        "@domainMin": domain[0], "@domainMax": domain[1],
        "axes": axes(("energy_in", "eV"), (quantity_label, unit)),
    }}


# ----- the GNDS document, as a Python dict -----


GNDS = {
    "_xml": {"version": "1.0", "encoding": "UTF-8"},
    "reactionSuite": {
        "@projectile": "n",
        "@target": "H1",
        "@evaluation": "demo",
        "@format": "2.1",
        "@projectileFrame": "lab",
        "@interaction": "nuclear",

        # --- styles: declares this is an "evaluated" data set ---
        "styles": {
            "evaluated": {
                "@label": "eval", "@date": "2026-05-28",
                "@library": "demo", "@version": "0.0.1",
                "temperature": {"@value": "0", "@unit": "K"},
                "projectileEnergyDomain": {
                    "@min": "1e-5", "@max": "2e7", "@unit": "eV",
                },
            },
        },

        # --- PoPs: properties of the particles referenced in the file ---
        "PoPs": {
            "@name": "demo_pops", "@version": "1.0", "@format": "2.1",
            "baryons": {"baryon": {
                "@id": "n",
                "mass":     {"double":   {"@label": "eval", "@value": "1.00866491574", "@unit": "amu"}},
                "spin":     {"fraction": {"@label": "eval", "@value": "1/2", "@unit": "hbar"}},
                "parity":   {"integer":  {"@label": "eval", "@value": "1"}},
                "charge":   {"integer":  {"@label": "eval", "@value": "0", "@unit": "e"}},
                "halflife": {"double":   {"@label": "eval", "@value": "881.5", "@unit": "s"}},
            }},
            "chemicalElements": {"chemicalElement": {
                "@symbol": "H", "@Z": "1", "@name": "Hydrogen",
                "isotopes": {"isotope": {
                    "@symbol": "H1", "@A": "1",
                    "nuclides": {"nuclide": {
                        "@id": "H1",
                        "mass":   {"double":  {"@label": "eval", "@value": "1.00782500046", "@unit": "amu"}},
                        "charge": {"integer": {"@label": "eval", "@value": "0", "@unit": "e"}},
                        "nucleus": {
                            "@id": "h1", "@index": "0",
                            "mass":     {"double":   {"@label": "eval", "@value": "1.00727646662", "@unit": "amu"}},
                            "spin":     {"fraction": {"@label": "eval", "@value": "1/2", "@unit": "hbar"}},
                            "parity":   {"integer":  {"@label": "eval", "@value": "1"}},
                            "charge":   {"integer":  {"@label": "eval", "@value": "1", "@unit": "e"}},
                            "halflife": {"string":   {"@label": "eval", "@value": "stable", "@unit": "s"}},
                            "energy":   {"double":   {"@label": "eval", "@value": "0.", "@unit": "eV"}},
                        },
                    }},
                }},
            }},
        },

        # --- the actual reaction: elastic scattering, MT=2 ---
        "reactions": {"reaction": {
            "@label": "n + H1", "@ENDF_MT": "2",

            # Cross section: flat 20.4 b across the energy domain
            # (two-point XYs1d expressed in space-delimited values).
            "crossSection": {"XYs1d": {
                "@label": "eval",
                "axes": axes(("energy_in", "eV"), ("crossSection", "b")),
                "values": "1e-5 20.4 2e7 20.4",
            }},

            # Output channel: two-body kinematics with the outgoing n and H1.
            "outputChannel": {
                "@genre": "twoBody",
                "Q": constant1d(0, quantity_label="Q", unit="eV"),
                "products": {"product": [
                    {
                        "@pid": "n", "@label": "n",
                        "multiplicity": constant1d(
                            1, quantity_label="multiplicity", unit=""),
                        # Isotropic angular distribution (a simple placeholder).
                        "distribution": {"angularTwoBody": {
                            "@label": "eval", "@productFrame": "centerOfMass",
                            "isotropic2d": {"axes": axes(
                                ("energy_in", "eV"),
                                ("mu", ""),
                                ("P(mu|energy_in)", ""),
                            )},
                        }},
                    },
                    {
                        "@pid": "H1", "@label": "H1",
                        "multiplicity": constant1d(
                            1, quantity_label="multiplicity", unit=""),
                        # Recoil: the H1's distribution mirrors the n's.
                        "distribution": {"angularTwoBody": {
                            "@label": "eval", "@productFrame": "centerOfMass",
                            "recoil": {"@href":
                                "../../../../product[@label='n']"
                                "/distribution/angularTwoBody[@label='eval']"},
                        }},
                    },
                ]},
            },
        }},
    },
}


# ----- main -----


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="Write the generated XML to this file in addition to printing it.")
    ap.add_argument("--skip-fudge", action="store_true",
                    help="Do not attempt the FUDGE verification step.")
    args = ap.parse_args(argv)

    xml = gndson.to_xml_string(GNDS)
    print(xml)

    if args.output is not None:
        args.output.write_text(xml, encoding="utf-8")
        print(f"\n[wrote {args.output}]", file=sys.stderr)

    if args.skip_fudge:
        return 0

    print("\n[FUDGE verification]", file=sys.stderr)
    try:
        from fudge import GNDS_file
    except ImportError:
        print("  FUDGE not available in this environment — skipping.", file=sys.stderr)
        print("  Re-run with a Python that has FUDGE installed to enable the check.",
              file=sys.stderr)
        return 0

    # FUDGE needs a file on disk to read.
    path = args.output if args.output is not None else Path("/tmp/gndson_minimal_demo.xml")
    if args.output is None:
        path.write_text(xml, encoding="utf-8")
    try:
        rs = GNDS_file.read(str(path))
    except Exception as e:
        print(f"  FUDGE read FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(f"  OK: {type(rs).__name__}", file=sys.stderr)
    print(f"  projectile={rs.projectile}, target={rs.target}, "
          f"format={rs.format}, {len(rs.reactions)} reaction(s)", file=sys.stderr)
    for r in rs.reactions:
        cs = r.crossSection.evaluated
        e = 1e6  # 1 MeV — a familiar reactor / fast-region energy
        print(f"  reaction {r.label!r} MT={r.ENDF_MT}: "
              f"cross section at {e:g} eV = {cs.evaluate(e):g} b",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
