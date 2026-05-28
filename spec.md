# GNDS XML ↔ JSON Translation Spec — Draft v0.5

All "GNDS PDF §X.Y" references in this document refer to:

> Mattoon, C., Gert, G., Holcomb, A., Brown, D., Wiarda, D., Chapman, C.,
> Haeck, W., Staley, M. (2025). *GNDS-2.1 Specifications.* NEA Working
> Paper NEA/WKP(2025)6, Nuclear Energy Agency, OECD.

## Scope

Translates GNDS XML files to/from a JSON representation with **perfect round-tripping up to non-encoding whitespace**: two XML files are *translator-equivalent* iff they produce identical JSON, and `untranslate(translate(X))` differs from `X` only in inter-tag whitespace, self-closing-vs-pair-form (modulo `_nocollapse`), attribute-quote character, attribute order (modulo `_attrorder`), and minimal entity re-escaping.

**Out of scope** (translator errors loudly on encounter):

- XML namespaces — `xmlns:` declarations and namespace-prefix *resolution*. Colons appearing literally in element or attribute names (e.g. the `xpath:href` form in GNDS PDF §13.2) are accepted as ordinary characters in the name; GNDS does not use XML namespaces semantically.
- DOCTYPE / entity definitions
- Processing instructions other than the XML declaration
- Mixed content of the form *text + element children interleaved* within the same element. GNDS itself forbids this (PDF §2.2: "no container requires a body with mixed text and nodes"); the restriction is part of the source format, not just a translator limitation. (Text + comment children IS supported — see §1 and §6.)
- Custom DTD entities
- External `href`-linked data is not followed (treated as a plain attribute string)
- HDF5 sidecar files

**Names are case-sensitive.** Per GNDS PDF §2.2: element names, attribute names, and attribute values are case-sensitive. The translator preserves case verbatim in both directions.

## 1. Element encoding

An XML element is encoded as one of two JSON forms:

| XML case | JSON encoding |
|---|---|
| No attributes, no element children, no comment children — only text content `T` (incl. `""`) | bare string `"T"` |
| Otherwise (any attributes, any element children, any comments, or text alongside attributes) | JSON object |

The object form contains, in any combination:

- `"@<name>": "<value>"` — one entry per XML attribute.
- `"<child-tag>": <encoding>` when that tag occurs exactly once under this parent.
- `"<child-tag>": [<enc₁>, …, <encₙ>]` when that tag occurs `N ≥ 2` times under this parent, in document order.
- Optional meta keys (all reserved-prefix `_`): see §2.

The `_text` meta key (see §2) carries the element's text content when the bare-string shortcut does not apply.

## 2. Meta keys

All optional unless required for fidelity. Translator emits the minimum needed.

| Key | Type | Purpose |
|---|---|---|
| `_order` | list of strings | **Semantic.** Sibling order within an element. Entries may be child tag names (one entry per occurrence), the literal `"_comment"` (consumes the next entry of `_comments`), or the literal `"_text"` (consumes the next entry of `_text` when `_text` is a list). Required only when child encounter order is not reconstructible from JSON insertion order + array list order — e.g. when distinct child tags interleave, when comments are present, or when text is split by comments. When present, `_order` overrides JSON insertion order on writeback. |
| `_attrorder` | list of strings | **Cosmetic.** Order of attribute names. Preserved for visual round-trip fidelity but not required for XML equivalence (XML 1.0 §3.1: attribute order is not significant). When present, `_attrorder` overrides JSON insertion order for attribute emission. |
| `_text` | string OR list of strings | Element's text content when the bare-string shortcut does not apply. **String form**: a single text segment (used for `text+attrs`, or for a text-only element that for some reason must be in object form). **List form**: multiple text segments, separated by comments; `_order` must contain one `"_text"` marker per segment in the correct interleaved position. |
| `_comments` | list of strings | XML comment texts in encounter order. Position-marked by `"_comment"` entries in `_order`. |
| `_cdata` | list of strings | Tag names whose text content is CDATA-encoded in XML. Applies to all occurrences of that tag under this parent. |
| `_nocollapse` | list of strings | Tag names that must be emitted as `<tag></tag>` (pair form) instead of `<tag/>` when empty. Default for empty elements is self-closing. |

**Always-list rule.** The keys `_order`, `_attrorder`, `_comments`, `_cdata`, `_nocollapse` are always JSON lists — even when they contain one entry. They are not subject to the scalar-vs-array shortening rule that applies to child-tag values (§1). Rationale: they are positionally indexed or treated as sets by consumers; a stable shape simplifies access. `_text` is the lone exception: it is a string in the common single-segment case and a list only when split by comments.

There is no `_arrays` key. Array-vs-scalar status of child tags is count-driven and lossy across the XML hop; see §9.

## 3. Document root

The top-level JSON object wraps the root XML element under its tag name, plus an optional XML declaration:

- `"<root-tag>": <encoding>` — **required.** The root element's encoding (always object form, since the root has children or attributes in any real GNDS file). The key is the XML root element's tag name (e.g. `"reactionSuite"`, `"covarianceSuite"`).
- `"_xml": {"version": "1.0", "encoding": "UTF-8"}` — optional. XML declaration metadata. If absent on write, defaults are used.

The top-level object must contain exactly one non-meta key (the root tag). Multiple non-meta keys, or zero, is a fatal error.

This wrapping is the one structural rhyme that elevates the root element to the same form as every other element: each element is encoded as `{<tagname>: <encoding>}` under its parent — and at the top level, the document plays the role of the parent.

## 4. Reserved name prefixes

- `@` — attribute names
- `_` — translator meta keys

Any XML attribute name beginning with `@`, or any child tag / attribute name colliding with a reserved meta key (`_order`, `_attrorder`, `_text`, `_comments`, `_cdata`, `_nocollapse`, `_xml`, `_comment`), is a fatal error.

## 5. Whitespace policy

- **Inter-tag whitespace** (between tags, indentation, line breaks outside text content): dropped on read; canonical pretty-print on write. Not part of round-trip contract.
- **Text content** (between an element's open and close tags, including CDATA bodies, and including each segment in a comment-split text): preserved **byte-exact** — newlines, tabs, leading/trailing whitespace.
- **Self-closing form** `<x/>` is the default for empty elements. Tags listed in the parent's `_nocollapse` are emitted as `<x></x>`.
- **Attribute quote** is `"` on output.
- **Attribute order** is preserved via JSON insertion order or explicit `_attrorder` (§2). The translator preserves order by default; portable JSON producers may use `_attrorder` to lock it in.

## 6. Comments

XML comments inside the root element are preserved:

1. Each comment's text is appended to the parent's `_comments` list in encounter order.
2. A `"_comment"` marker is inserted into the parent's `_order` at the corresponding position.

Comments may appear:

- Among element children (the common case).
- Inside a text-only element, splitting the text into multiple segments. The element is encoded in object form, with `_text` as a list of segments and `_order` interleaving `"_text"` and `"_comment"` markers.
- Multiple times and in any positions (adjacent comments are supported: two consecutive `"_comment"` markers in `_order`).

Comments outside the root element (before/after) are not preserved. Comments inside a CDATA section are part of the CDATA text, not separate comments.

## 7. CDATA

Tags listed in the parent's `_cdata` have their text content emitted inside `<![CDATA[...]]>`. CDATA-ness is at tag-name granularity within a parent — all occurrences of a same-named tag in that parent are CDATA or all are not. Per-occurrence variation is a fatal error.

## 8. Entities

The XML predefined entities `&amp;`, `&lt;`, `&gt;`, `&quot;`, `&apos;` are decoded into JSON strings on read and minimally re-encoded on write (only where the literal character would be syntactically invalid in its context). The encoder is pluggable so users can change the policy without modifying the core.

Custom DTD-defined entities are not supported (see §Scope).

## 9. Round-trip contract

```
translate    : XML → JSON
untranslate  : JSON → XML
```

**Canonical JSON form.** The form produced by `translate`. In particular:

- Child-tag values are scalars when the child occurs once and lists when it occurs `N ≥ 2` times.
- `_text` is a string when there is exactly one text segment and a list only when split by comments.
- Meta keys appear only when needed for fidelity (e.g., `_order` is omitted when JSON insertion order already captures the right order).

**XML equivalence.** Two XML documents are equivalent iff they differ only in inter-tag whitespace, self-closing-vs-pair-form (modulo `_nocollapse`), attribute quote character, attribute order (modulo `_attrorder`), and minimal entity re-escaping.

**Semantic vs. textual equivalence.** This spec defines *textual* equivalence — the bytes the translator produces. GNDS *semantic* equivalence is broader: many GNDS attributes have defaults (`interpolation="lin-lin"`, `compression="none"`, `storageOrder="row-major"`, `sep="whiteSpace"`, etc.; GNDS PDF §2 line 1096: "a required value does not have to be specified if it has a default value"). Two GNDS files differing only in whether default-valued attributes are explicitly written are semantically equal but textually different — and the translator preserves that textual difference. Canonicalising to a default-omitting or default-explicit form is intentionally NOT performed; it would require GNDS schema knowledge the translator does not have.

**Round-trip guarantee.**

- For any in-scope GNDS XML `X`: `untranslate(translate(X))` is XML-equivalent to `X`.
- For any canonical JSON `J`: `translate(untranslate(J))` equals `J`.

**1-element-list equivalence (JSON normalization).** A JSON document containing a 1-element list `[v]` under a child-tag key is *translator-equivalent* to the same document with that list replaced by the scalar `v`. The canonical form is the scalar; `translate` emits only the canonical form, and `untranslate` accepts either form (both produce the same XML).

> Consequence: schema-driven "always array" information cannot survive the XML hop without external schema knowledge. A user may hand-author JSON with 1-element lists for type stability, but the round-trip will normalize to scalar. JSON consumers requiring uniform typing must use defensive coding or external schema.

**Order overrides.** When `_order` is present, it determines the document order of child elements, comments, and text segments on writeback, overriding JSON insertion order and any list-order. When `_attrorder` is present, it determines attribute emission order, overriding JSON insertion order. Both keys can be omitted in canonical output because the translator preserves insertion order by default.

## 10. Error policy

The translator errors loudly (never silently transforms data) when it encounters:

- Any out-of-scope XML feature (§Scope).
- A name collision with reserved prefixes (§4).
- Per-occurrence CDATA variation for a repeated tag (§7).
- A custom DTD entity (§8).
- A meta key with malformed shape — e.g. `_cdata` not a list of strings, `_order` referencing children that do not exist, `_order` `_comment`-count not matching `_comments` length, `_order` `_text`-count not matching `_text` list length, `_attrorder` not a permutation of the element's attribute names.
- `_text` present as a list when `_order` does not interleave `_text` markers correctly, or as a string when comments split the text content.
- A top-level JSON object with zero or more than one non-meta key (§3 requires exactly one — the root tag).

---

## Worked examples

### Example 1: typical structure

XML:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<reactionSuite projectile="n" target="H1">
  <reactions>
    <!-- elastic -->
    <reaction label="n + H1" ENDF_MT="2">
      <crossSection>
        <function1ds>
          <XYs1d index="0"><values>1.0 2.0 3.0</values></XYs1d>
          <XYs1d index="1"><values>4.0 5.0 6.0</values></XYs1d>
        </function1ds>
      </crossSection>
    </reaction>
  </reactions>
</reactionSuite>
```

JSON (canonical):

```json
{
  "_xml": {"version": "1.0", "encoding": "UTF-8"},
  "reactionSuite": {
    "@projectile": "n",
    "@target": "H1",
    "reactions": {
      "_order": ["_comment", "reaction"],
      "_comments": ["elastic"],
      "reaction": {
        "@label": "n + H1",
        "@ENDF_MT": "2",
        "crossSection": {
          "function1ds": {
            "XYs1d": [
              {"@index": "0", "values": "1.0 2.0 3.0"},
              {"@index": "1", "values": "4.0 5.0 6.0"}
            ]
          }
        }
      }
    }
  }
}
```

Notes:

- The root element `<reactionSuite>` is wrapped under a top-level `"reactionSuite"` key — see §3.
- `<values>1.0 2.0 3.0</values>` is text-only-no-attr-no-comment → bare string.
- `<XYs1d>` repeats → JSON list.
- `<reactions>` requires `_order` only because a comment interleaves with `reaction`; otherwise it would be omitted.
- Attribute order (`@projectile` before `@target`) is preserved by JSON insertion order alone; `_attrorder` is unnecessary.

### Example 2: comment splitting text content

(Pattern, not tag-specific: triggered by any text-only element that contains comment children. In the corpus this appears in `<data>` with `sep="whiteSpace"` mode — see notes below for other `<data>` modes.)

XML:

```xml
<data>
  <!-- energy | L | J | totalWidth | neutronWidth | captureWidth -->
       -10740   0   0.5     102.6217       101.7507          0.871
       147400   1   0.5     945.1834       941.4834            3.7
</data>
```

JSON:

```json
"data": {
  "_order": ["_text", "_comment", "_text"],
  "_text": [
    "\n  ",
    "\n       -10740   0   0.5     102.6217       101.7507          0.871\n       147400   1   0.5     945.1834       941.4834            3.7\n"
  ],
  "_comments": [" energy | L | J | totalWidth | neutronWidth | captureWidth "]
}
```

Notes:

- `<data>` here (in `sep="whiteSpace"` mode) has no attributes and no element children, but it has a comment child, so the bare-string shortcut does NOT apply.
- The two text segments are stored in `_text` (list form).
- `_order` interleaves `"_text"` and `"_comment"` markers; positional consumption pairs the i-th `"_text"` with `_text[i]` and the i-th `"_comment"` with `_comments[i]`.
- Both text segments are preserved byte-exact, including newlines and indentation.
- In `sep="td"` / `"tr"` / `"tc"` modes, `<data>` instead contains real `<td>` / `<tr>` / `<tc>` element children — those are covered by the generic element-encoding rules in §1 with no special handling needed.

---

## Changelog

**v0.5** — fixed an oversight in §3: the top-level JSON object now wraps the root element under its tag name rather than collapsing the root encoding into the document object. Without the wrap, the root element's tag name was nowhere in the JSON and could not be recovered on writeback. Example 1 updated. §10 gains a new error case (top-level must contain exactly one non-meta key).

**v0.4** — clarified that colons in element/attribute names are accepted as literal characters (the `xpath:href` form in GNDS PDF §13.2), not parsed as namespace prefixes. Added a one-line case-sensitivity callout (Scope). Added a Semantic-vs-Textual equivalence note in §9 stating that default-valued-attribute normalization is intentionally NOT performed. Reframed Example 2 from "the `<data>` case" to the general "comment splitting text content" pattern, with a note that `<data>` in `sep="td"|"tr"|"tc"` modes uses ordinary element children covered by §1. Noted that GNDS itself bans mixed text + element-children content (not just the translator).

**v0.3** — added support for text + comment mixing inside otherwise text-only elements (`<data>` case): `_text` may be a string or a list of strings; `_order` may contain `"_text"` markers. Added `_attrorder` (cosmetic attribute-order key). Tightened bare-string condition to exclude elements with comment children. Clarified always-list rule for meta keys (with `_text` as the documented exception). Specified `_order` and `_attrorder` override JSON insertion order on writeback.

**v0.2** — removed `_arrays` key; codified count-driven scalar-vs-list encoding for child tags; documented 1-element-list ≡ scalar JSON normalization.

**v0.1** — initial draft.
