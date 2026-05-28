# gndson

Round-trip translator between **GNDS XML** and a clean, JSON-native representation.

> ⚠️ **Early alpha (`0.1.0a1`).** gndson is a prototype. The JSON encoding,
> the schema-pipeline names, and the public Python and CLI interfaces may
> change without notice between minor versions. The XML ↔ JSON round-trip
> contract (`spec.md` §9) is the stable commitment; everything else may evolve.
> Pin a specific version if you depend on it.

`gndson` lets you work with GNDS files as ordinary JSON — read, edit,
diff, search with `jq` — and round-trip them back to XML without losing anything.

The test corpus used during development is every file of the **FENDL 3.2c
neutron sub-library** that was successfully converted to GNDS XML — 145
files in total (~1.6M XML elements), covering both `reactionSuite` and
`covarianceSuite` documents. The translator is verified on this corpus
at two levels:

- **Spec-equivalence** (per `spec.md` §9): 145/145 (100%)
- **Byte-form-strict** (also preserves `<x/>` vs `<x></x>`): 145/145 (100%)

## Background

GNDS (Generalised Nuclear Database Structure) is the modern XML-based format
for evaluated nuclear data, developed under the WPEC EGNDS group and intended
as the successor to the long-serving ENDF-6 fixed-column text format. A GNDS
document organises reactions, cross sections, distributions, covariances, and
metadata in a single hierarchical structure. The current normative
specification is:

> Mattoon, C., Gert, G., Holcomb, A., Brown, D., Wiarda, D., Chapman, C.,
> Haeck, W., Staley, M. (2025). *GNDS-2.1 Specifications.* NEA Working
> Paper NEA/WKP(2025)6, Nuclear Energy Agency, OECD.

gndson tracks this revision; all section references in `spec.md` and
`framework.md` cite it.

XML is rich and self-describing, but JSON is the lingua franca of modern
tooling — every browser, every scripting language, every data-science stack
reads JSON natively, every diff tool understands it, every cloud database
stores it. Bringing GNDS within reach of that ecosystem is what gndson is for.

gndson is a **mechanistic, bijective translator** between GNDS XML and JSON.
It carries no opinion about what the data *should* look like — it preserves
whatever the source XML expressed and emits JSON that reconstructs the same
XML on the round trip. Schema-aware ergonomic transformations live in a
separate layer above the bijective core, opt-in by name (see "Schema-aware
ergonomic output" below).

Because the translation is mechanical, it does **not** interfere with the
work of the WPEC EGNDS group on the GNDS specification itself. Any future
addition to the GNDS XML schema — new elements, new attributes, new
structural patterns — is automatically reflected in the JSON representation
without changes to gndson, and the schema-aware layer can be extended to
recognise new patterns as they are formalised.

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
gndson verify file.xml                              # XML round-trip (spec-equivalence)
gndson verify file.xml --strict                     # also require byte-form fidelity
gndson verify file.xml --pipeline ergonomic        # also verify schema-layer round-trip
gndson verify file.xml --pipeline ergonomic_full --strict   # all three checks
```

`verify` exits 0 on success, 1 on a round-trip mismatch, 2 on a translator error.
When `--pipeline NAME` is given, the schema-layer check
(`pipeline.inverse(pipeline.forward(canonical)) == canonical`) runs in addition
to the XML-layer check.

### Compose in a pipe

```bash
cat file.xml | gndson xml-to-json | gndson json-to-xml > round.xml
```

### Schema-aware ergonomic output

`xml-to-json`, `json-to-xml`, and `verify` accept `--pipeline NAME` to apply
one of the named schema-layer pipelines (see `framework.md`). On `xml-to-json`
the pipeline's forward direction runs after parsing; on `json-to-xml` the
inverse runs before serialising; on `verify` the schema-layer round-trip is
checked alongside the XML-layer one.

Available pipelines, smallest to fullest:

| Pipeline               | What it does                                                                   |
|------------------------|--------------------------------------------------------------------------------|
| `canonical`            | identity — no schema transformation                                            |
| `arity`                | always-list discipline for plural containers (`reactions/reaction`, ...)       |
| `uniform`              | `arity` + collapse `{Xs: {X: [...]}}` to `{Xs: [...]}` for uniform-inner       |
| `wrappers`             | annotate physicalQuantity wrappers with `_kind` and collapse them              |
| `heterogeneous`        | collapse heterogeneous containers (`function1ds`, `styles`, `axes`, ...) to a flat list with `_kind` per item |
| `split_text`           | split `<values>` text into a JSON list of tokens                               |
| `data_columns`         | parse FUDGE-style `<data>` header comments into `_columns` + `_rows`           |
| `ergonomic`            | `arity` + `uniform` + `wrappers` — the recommended default                     |
| `ergonomic_full`       | `ergonomic` + `heterogeneous`                                                  |
| `ergonomic_split`      | `ergonomic_full` + `split_text`                                                |
| `ergonomic_split_data` | `ergonomic_split` + `data_columns` — the fullest ergonomic form                |

All pipelines round-trip 145/145 on the bundled GNDS corpus (the
`split_text`-containing pipelines round-trip at the GNDS-spec level —
internal whitespace inside `<values>` bodies is normalised on the inverse).

Per-pipeline documentation with worked before/after examples,
witness-flow tables, and inverse instructions lives under
[`docs/pipelines/`](docs/pipelines/) — auto-generated by `gndson docs
--all`. CI gating is `gndson docs --all --check`.

```bash
gndson xml-to-json file.xml --pipeline ergonomic              # the recommended default
gndson xml-to-json file.xml --pipeline ergonomic_split_data   # fullest ergonomic form
gndson json-to-xml file.json --pipeline ergonomic_split_data  # inverse: take a JSON
                                                              # produced by the same
                                                              # pipeline back to XML
gndson verify file.xml --pipeline ergonomic_full --strict     # all three checks
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

`examples/roundtrip_through_fudge.py` proves *round-trip identity*: for one or
more input files it reads the ORIGINAL with FUDGE and the gndson-round-tripped
version with FUDGE, then compares both `toXML()` outputs (via gndson's own
faithful comparator) AND the cross-section values evaluated at sample energies.
FUDGE cannot tell the original from the round-trip.

The first two scripts skip the FUDGE step gracefully when FUDGE isn't
importable; pass `--skip-fudge` to skip it explicitly. The third requires FUDGE
(it is the whole point).

## Specification

See `spec.md` for the canonical-form definition, the round-trip contract, and the
reasoning behind individual design decisions.

## Design principles

See `framework.md` for the broader operations / witnesses / round-trip-oracle
framework that gndson is built on. Useful for deciding whether a new feature
belongs in the translator, in a schema-augmentation layer above it, or in a
user-facing reduction.

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
