# gndson

Round-trip translator between **GNDS XML** and a clean, JSON-native representation.

GNDS (Generalised Nuclear Database Structure) is the XML format used by nuclear data
evaluators. `gndson` lets you work with GNDS files as ordinary JSON — read, edit,
diff, search with `jq` — and round-trip them back to XML without losing anything.

Across the GNDS corpus (145 files, ~1.6M elements) the translator is verified at
two levels:

- **Spec-equivalence** (per `spec.md` §9): 145/145 (100%)
- **Byte-form-strict** (also preserves `<x/>` vs `<x></x>`): 145/145 (100%)

## Install

The package is pure Python (>=3.7), no external dependencies:

```bash
pip install -e .
```

For development (runs the test suite via `pytest`):

```bash
python -m venv venv
./venv/bin/pip install -e .[test]
```

## CLI

Three subcommands; each reads from `stdin` and writes to `stdout` by default.

### Translate XML to JSON

```bash
gndson xml-to-json file.xml                    # JSON on stdout
gndson xml-to-json file.xml -o file.json       # write to file
gndson xml-to-json file.xml --indent -1        # compact (one line)
cat file.xml | gndson xml-to-json              # stdin
```

### Translate JSON back to XML

```bash
gndson json-to-xml file.json -o out.xml
```

### Verify round-trip on a single file

```bash
gndson verify file.xml             # spec-equivalence
gndson verify file.xml --strict    # also require byte-form fidelity
```

`verify` exits 0 on success, 1 on a round-trip mismatch, 2 on a translator error.

### Compose in a pipe

```bash
cat file.xml | gndson xml-to-json | gndson json-to-xml > round.xml
```

`python -m gndson <command> ...` works identically if you prefer not to install.

## Python API

```python
import gndson

# XML -> JSON-shaped dict
data = gndson.parse_xml_file("file.xml")
# or
data = gndson.parse_xml_bytes(open("file.xml", "rb").read())

# JSON-shaped dict -> XML
xml_text = gndson.to_xml_string(data)
# or write directly
gndson.write_xml_file(data, "out.xml")
```

The returned `data` is a plain Python `dict` / `list` / `str` tree — there is no
wrapper class to learn. Standard `json` module reads and writes it directly.

### Encoding rules at a glance

```python
data = gndson.parse_xml_bytes(
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<r a="1"><x>hello</x><x>world</x></r>'
)
# data == {
#   "_xml": {"version": "1.0", "encoding": "UTF-8"},
#   "r": {
#     "@a": "1",                # attributes: prefix '@'
#     "x": ["hello", "world"],  # repeated tag -> list
#   }
# }
```

Element-encoding rules (see `spec.md` for the full definition):

| XML | JSON |
|---|---|
| `<x>hello</x>` (text only, no attrs) | bare string `"hello"` |
| `<x a="1"/>` (attrs only) | `{"@a": "1"}` |
| `<x>foo</x>` once, `<x>bar</x>` twice | `"x": "foo"` (scalar) or `"x": ["foo","bar"]` (list) — by count |
| `<![CDATA[...]]>` text | normal string + parent has `_cdata: ["x"]` |
| `<!-- comment -->` | parent has `_comments: ["comment"]` + `_order: [..., "_comment", ...]` |
| `<x></x>` (explicit empty pair) | empty string + parent has `_nocollapse: ["x"]` |

All meta keys are reserved-prefix `_` so they cannot collide with GNDS tag names.

## Round-trip contract

Translator-equivalence (per `spec.md` §9): two XML files are equivalent iff they
differ only in:

- inter-tag whitespace
- self-closing-vs-pair form, modulo `_nocollapse`
- attribute order, modulo `_attrorder`
- attribute quote character
- minimal entity escaping

Everything else — text content (byte-exact), CDATA-ness, comments, child order,
attributes — is faithfully preserved.

## Tests

```bash
./venv/bin/pytest                                              # unit tests (~85)
./venv/bin/pytest --gnds-corpus /path/to/gnds/xml/files        # also run corpus
./venv/bin/python tests/test_roundtrip_corpus.py /path/to/dir  # corpus, script mode
```

The corpus driver reports two pass rates: spec-equivalence and byte-form-strict
(see "Round-trip contract" above).

## Examples

`examples/build_minimal_from_json.py` hand-authors a one-reaction GNDS file
(n + H-1 elastic, MT=2) as a Python dict, translates it to XML with `gndson`,
and (if FUDGE is importable) reads the result back to confirm the cross section
value.

`examples/edit_via_json.py` shows the "edit nuclear data as JSON" workflow:
loads a corpus GNDS file, scales a cross section in JSON-land via ordinary dict
indexing, writes the modified XML, and uses FUDGE to confirm the change is
visible (`σ(1 MeV) = 4.25 b` → `8.49 b` after `--factor 2.0`).

Both scripts skip the FUDGE step gracefully when FUDGE isn't importable; pass
`--skip-fudge` to skip it explicitly.

## Specification

See `spec.md` for the canonical-form definition, the round-trip contract, and the
reasoning behind individual design decisions.

## Layout

```
gndson/
  __init__.py     # public API
  __main__.py     # CLI
  parser.py       # XML -> canonical JSON dict (expat-based)
  serializer.py   # canonical JSON dict -> XML
  entities.py     # pluggable XML entity codec
  errors.py       # exception hierarchy
  _compare.py     # faithful XML comparator for round-trip checks
  _meta.py        # reserved-name constants
tests/
  test_features.py            # unit tests per spec rule
  test_cli.py                 # CLI smoke tests
  test_roundtrip_corpus.py    # corpus-driver round-trip test
spec.md           # the format specification
```
