"""Smoke tests for the gndson CLI."""

import io
import json
import sys
from pathlib import Path

import pytest

from gndson.__main__ import build_parser, main


SAMPLE_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<root a="1"><child>hello</child><child>world</child></root>'
)


class _FakeStdin:
    """Minimal stand-in: exposes `.buffer` of type BytesIO, which is what the
    CLI reads from. The CLI never touches stdin's text-mode interface."""

    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


def _run(argv, stdin: bytes = b"") -> tuple[int, str, str]:
    """Run the CLI as if from the command line. Captures stdout / stderr."""
    saved_in, saved_out, saved_err = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = _FakeStdin(stdin)  # type: ignore[assignment]
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        rc = main(argv)
    finally:
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        sys.stdin, sys.stdout, sys.stderr = saved_in, saved_out, saved_err
    return rc, out, err


def test_xml_to_json_stdin_stdout():
    rc, out, _ = _run(["xml-to-json"], stdin=SAMPLE_XML)
    assert rc == 0
    obj = json.loads(out)
    assert obj["root"]["@a"] == "1"
    assert obj["root"]["child"] == ["hello", "world"]


def test_xml_to_json_compact(tmp_path):
    p = tmp_path / "in.xml"
    p.write_bytes(SAMPLE_XML)
    rc, out, _ = _run(["xml-to-json", str(p), "--indent", "-1"])
    assert rc == 0
    assert "\n" not in out.rstrip()  # compact, single line


def test_json_to_xml_file_out(tmp_path):
    obj = {"_xml": {"version": "1.0", "encoding": "UTF-8"},
           "root": {"@a": "1", "child": ["hello", "world"]}}
    p_in = tmp_path / "in.json"
    p_out = tmp_path / "out.xml"
    p_in.write_text(json.dumps(obj), encoding="utf-8")
    rc, _, _ = _run(["json-to-xml", str(p_in), "-o", str(p_out)])
    assert rc == 0
    text = p_out.read_text(encoding="utf-8")
    assert "<child>hello</child>" in text
    assert "<child>world</child>" in text
    assert 'a="1"' in text


def test_round_trip_via_cli(tmp_path):
    """End-to-end: xml -> json -> xml gives an equivalent file."""
    p_xml = tmp_path / "src.xml"
    p_json = tmp_path / "mid.json"
    p_xml2 = tmp_path / "back.xml"
    p_xml.write_bytes(SAMPLE_XML)
    assert _run(["xml-to-json", str(p_xml), "-o", str(p_json)])[0] == 0
    assert _run(["json-to-xml", str(p_json), "-o", str(p_xml2)])[0] == 0
    assert _run(["verify", str(p_xml)])[0] == 0
    assert _run(["verify", str(p_xml), "--strict"])[0] == 0


def test_verify_reports_failure(tmp_path):
    # Feed malformed JSON-roundtrip: we'd need a file that exercises an
    # unsupported feature. Use a DOCTYPE to trip UnsupportedXmlError.
    p = tmp_path / "bad.xml"
    p.write_bytes(b"<!DOCTYPE r><r/>")
    rc, _, err = _run(["verify", str(p)])
    assert rc == 2
    assert "UnsupportedXmlError" in err


def test_parser_help_smoke():
    ap = build_parser()
    text = ap.format_help()
    assert "xml-to-json" in text
    assert "json-to-xml" in text
    assert "verify" in text
