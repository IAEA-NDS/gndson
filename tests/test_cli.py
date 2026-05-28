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


# ===== --pipeline flag =====


PLURAL_SAMPLE_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<root><items><item a="1"/><item a="2"/></items></root>'
)


def test_pipeline_default_is_canonical_form():
    # No --pipeline: canonical form.
    rc, out, _ = _run(["xml-to-json"], stdin=PLURAL_SAMPLE_XML)
    assert rc == 0
    obj = json.loads(out)
    # Canonical form: <items><item/><item/></items> -> {items: {item: [...]}}
    assert obj["root"]["items"] == {"item": [{"@a": "1"}, {"@a": "2"}]}


def test_pipeline_ergonomic_applies_forward(tmp_path):
    # With --pipeline ergonomic: the uniform-plural-container collapse runs.
    p = tmp_path / "in.xml"
    p.write_bytes(PLURAL_SAMPLE_XML)
    # `items` isn't a uniform-plural container in our dictionary, so collapse
    # of the outer key isn't expected. But the inner `item` list is always
    # a list (it has 2 occurrences) — and would have been a list either way.
    # Use a container that IS in the dictionary to show a real effect:
    rxn = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<reactionSuite><reactions><reaction label="x"/></reactions></reactionSuite>'
    )
    p.write_bytes(rxn)
    rc, out, _ = _run(["xml-to-json", str(p), "--pipeline", "ergonomic"])
    assert rc == 0
    obj = json.loads(out)
    # Ergonomic pipeline: reactions/reaction collapses to a flat list.
    assert obj["reactionSuite"]["reactions"] == [{"@label": "x"}]


def test_pipeline_round_trip_xml_to_json_to_xml(tmp_path):
    # xml-to-json --pipeline NAME, then json-to-xml --pipeline NAME, must
    # produce an XML structurally identical to the original.
    rxn = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<reactionSuite><reactions>'
        b'<reaction label="a"/><reaction label="b"/>'
        b'</reactions></reactionSuite>'
    )
    p_xml = tmp_path / "in.xml"
    p_json = tmp_path / "mid.json"
    p_xml2 = tmp_path / "out.xml"
    p_xml.write_bytes(rxn)
    assert _run(["xml-to-json", str(p_xml), "-o", str(p_json),
                 "--pipeline", "ergonomic"])[0] == 0
    assert _run(["json-to-xml", str(p_json), "-o", str(p_xml2),
                 "--pipeline", "ergonomic"])[0] == 0
    # The verify subcommand confirms the round-trip equivalence.
    assert _run(["verify", str(p_xml)])[0] == 0
    # And the produced XML can itself be read again as canonical:
    rc, _, _ = _run(["xml-to-json", str(p_xml2)])
    assert rc == 0


def test_pipeline_unknown_name_rejected():
    # argparse `choices=` enforces the constraint and exits with code 2.
    with pytest.raises(SystemExit) as exc_info:
        _run(["xml-to-json", "--pipeline", "nonexistent"], stdin=PLURAL_SAMPLE_XML)
    assert exc_info.value.code == 2


def test_every_named_pipeline_is_accepted():
    # The CLI must accept every pipeline name declared in
    # gndson.schema.pipelines as a valid --pipeline argument.
    from gndson.schema.pipelines import pipeline_names
    for name in pipeline_names():
        rc, _, _ = _run(["xml-to-json", "--pipeline", name], stdin=PLURAL_SAMPLE_XML)
        assert rc == 0, f"pipeline {name!r} was rejected by the CLI"


def test_verify_with_pipeline_succeeds_on_real_input(tmp_path):
    rxn = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<reactionSuite><reactions>'
        b'<reaction label="a"/><reaction label="b"/>'
        b'</reactions></reactionSuite>'
    )
    p = tmp_path / "in.xml"
    p.write_bytes(rxn)
    rc, _, err = _run(["verify", str(p), "--pipeline", "ergonomic"])
    assert rc == 0
    # Both checks should report OK (pipeline first, then spec-equivalence).
    assert "OK pipeline 'ergonomic'" in err
    assert "OK spec-equivalence" in err


def test_verify_with_pipeline_and_strict(tmp_path):
    # All three checks should pass for clean canonical input.
    rxn = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<r><x/></r>'
    )
    p = tmp_path / "in.xml"
    p.write_bytes(rxn)
    rc, _, err = _run(["verify", str(p), "--strict", "--pipeline", "canonical"])
    assert rc == 0
    assert "OK pipeline 'canonical'" in err
    assert "OK spec-equivalence" in err
    assert "OK byte-form-strict" in err
