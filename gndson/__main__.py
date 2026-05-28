"""
Command-line interface for gndson.

Usage:
    gndson xml-to-json [INPUT] [-o OUTPUT] [--indent N] [--pipeline NAME]
    gndson json-to-xml [INPUT] [-o OUTPUT] [--pipeline NAME]
    gndson verify INPUT [--strict]

INPUT defaults to stdin (or '-'); --output defaults to stdout.

`--pipeline NAME` (on xml-to-json and json-to-xml) applies a named
schema-layer transformation pipeline. On xml-to-json the pipeline's
forward direction runs on the canonical JSON; on json-to-xml the
inverse runs first, restoring canonical before serialising back to
XML. Available pipelines: see `gndson.schema.pipelines.PIPELINES`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .errors import GndsonError
from .parser import parse_xml_bytes
from .schema.pipelines import PIPELINES, get_pipeline, pipeline_names
from .serializer import to_xml_string


# ----- helpers -----


def _read_input(path: str | None) -> bytes:
    """Read input bytes from a path or stdin."""
    if path is None or path == "-":
        return sys.stdin.buffer.read()
    return Path(path).read_bytes()


def _write_output(path: str | None, data: str) -> None:
    """Write string output to a path or stdout."""
    if path is None or path == "-":
        sys.stdout.write(data)
        if not data.endswith("\n"):
            sys.stdout.write("\n")
    else:
        Path(path).write_text(data, encoding="utf-8")


# ----- subcommands -----


def cmd_xml_to_json(args: argparse.Namespace) -> int:
    raw = _read_input(args.input)
    obj = parse_xml_bytes(raw)
    if args.pipeline:
        obj = get_pipeline(args.pipeline).forward(obj)
    if args.indent < 0:
        out = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    else:
        out = json.dumps(obj, ensure_ascii=False, indent=args.indent)
    _write_output(args.output, out)
    return 0


def cmd_json_to_xml(args: argparse.Namespace) -> int:
    raw = _read_input(args.input)
    text = raw.decode("utf-8")
    obj = json.loads(text)
    if args.pipeline:
        obj = get_pipeline(args.pipeline).inverse(obj)
    out = to_xml_string(obj)
    _write_output(args.output, out)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify round-trip property on a single XML file.

    Spec-equivalence by default; --strict additionally requires byte-form fidelity.
    """
    # Import lazily so the comparator is only loaded when the verify subcommand runs.
    from ._compare import parse_faithful, diff_summary

    raw = _read_input(args.input)
    try:
        obj = parse_xml_bytes(raw)
        re_xml = to_xml_string(obj).encode("utf-8")
    except GndsonError as e:
        print(f"translate error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    spec_a = parse_faithful(raw)
    spec_b = parse_faithful(re_xml)
    if spec_a != spec_b:
        print("FAIL spec-equivalence: " + diff_summary(spec_a, spec_b), file=sys.stderr)
        return 1
    print("OK spec-equivalence", file=sys.stderr)

    if args.strict:
        strict_a = parse_faithful(raw, strict_form=True)
        strict_b = parse_faithful(re_xml, strict_form=True)
        if strict_a != strict_b:
            print("FAIL byte-form-strict: " + diff_summary(strict_a, strict_b), file=sys.stderr)
            return 1
        print("OK byte-form-strict", file=sys.stderr)
    return 0


# ----- entry point -----


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="gndson",
        description="Round-trip translator between GNDS XML and JSON.",
    )
    ap.add_argument("--version", action="version", version=f"gndson {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="<command>")

    p = sub.add_parser("xml-to-json", help="Translate GNDS XML to canonical JSON.")
    p.add_argument("input", nargs="?", default=None,
                   help="Input XML file (default: stdin; '-' also means stdin).")
    p.add_argument("-o", "--output", default=None,
                   help="Output JSON file (default: stdout).")
    p.add_argument("--indent", type=int, default=2, metavar="N",
                   help="JSON indent width (default: 2; -1 for compact).")
    p.add_argument("--pipeline", choices=pipeline_names(), default=None,
                   metavar="NAME",
                   help=("Apply a named schema-layer pipeline to the parsed JSON "
                         "(default: none — emit canonical form). Available: "
                         + ", ".join(pipeline_names())))
    p.set_defaults(func=cmd_xml_to_json)

    p = sub.add_parser("json-to-xml", help="Translate canonical JSON to GNDS XML.")
    p.add_argument("input", nargs="?", default=None,
                   help="Input JSON file (default: stdin; '-' also means stdin).")
    p.add_argument("-o", "--output", default=None,
                   help="Output XML file (default: stdout).")
    p.add_argument("--pipeline", choices=pipeline_names(), default=None,
                   metavar="NAME",
                   help=("Apply the inverse of a named schema-layer pipeline before "
                         "serialising (use when the input JSON is in pipeline-output "
                         "form rather than canonical). Available: "
                         + ", ".join(pipeline_names())))
    p.set_defaults(func=cmd_json_to_xml)

    p = sub.add_parser("verify", help="Check the round-trip property on a GNDS XML file.")
    p.add_argument("input", nargs="?", default=None,
                   help="Input XML file (default: stdin).")
    p.add_argument("--strict", action="store_true",
                   help="Also require byte-form fidelity (self-closing-vs-pair).")
    p.set_defaults(func=cmd_verify)

    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except GndsonError as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
