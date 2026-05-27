"""
XML -> canonical JSON dict, per spec.md.

Iteration 2 — supports everything in iteration 1, plus:
  - _cdata: CDATA section detection on read; per-tag granularity per parent.

Iteration 1 baseline:
  - Elements, attributes, text content (incl. attribute order)
  - Top-level root-tag wrapping (spec §3)
  - Bare-string shortcut for text-only-no-attr-no-children elements (§1)
  - Object form with @-prefixed attributes (§1)
  - Scalar-vs-list child encoding by count (§1)
  - _text key for text alongside attributes (§2; reserved case B1)
  - _xml declaration metadata (§3)

Not yet implemented (planned for later iterations):
  - _comments / _order (comment preservation)
  - _nocollapse (explicit <x></x> vs <x/> distinction)
  - _text as list (text split by comments)
  - _attrorder (cosmetic attribute order)
"""

import xml.parsers.expat as expat
from typing import Any, Dict, List, Tuple

from ._meta import RESERVED_META, ATTR_PREFIX
from .errors import (
    UnsupportedXmlError,
    NameCollisionError,
    MixedContentError,
    CdataInconsistencyError,
)


def parse_xml_file(path: str) -> Dict[str, Any]:
    """Parse a GNDS XML file into a canonical JSON-shaped dict."""
    with open(path, "rb") as f:
        return parse_xml_bytes(f.read())


def parse_xml_bytes(data: bytes) -> Dict[str, Any]:
    """Parse GNDS XML bytes into a canonical JSON-shaped dict."""
    return _XmlToJson().parse(data)


# ----- internal -----


class _ElementRecord:
    """Mutable state held on the stack during parsing of a single element."""

    __slots__ = ("tag", "attrs", "children", "pending_text", "pending_is_cdata")

    def __init__(self, tag: str, attrs: Dict[str, str]) -> None:
        self.tag = tag
        self.attrs = attrs
        # Children list of (kind, payload):
        #   ("text", str)                            — plain-text run
        #   ("cdata_text", str)                      — CDATA-section text run
        #   ("elem", (tagname, encoded_value, child_is_cdata))
        # Later iterations add: ("comment", str).
        self.children: List[Tuple[str, Any]] = []
        self.pending_text = ""
        self.pending_is_cdata = False

    def flush_text(self) -> None:
        if self.pending_text:
            kind = "cdata_text" if self.pending_is_cdata else "text"
            self.children.append((kind, self.pending_text))
            self.pending_text = ""

    def set_cdata_state(self, in_cdata: bool) -> None:
        """Toggle the CDATA flag, flushing the pending run if its state changes."""
        if self.pending_is_cdata != in_cdata:
            self.flush_text()
            self.pending_is_cdata = in_cdata

    def add_elem(self, tagname: str, value: Any, child_is_cdata: bool) -> None:
        self.flush_text()
        self.children.append(("elem", (tagname, value, child_is_cdata)))


class _XmlToJson:
    """Expat-driven SAX handler that builds the canonical dict."""

    def __init__(self) -> None:
        self.stack: List[_ElementRecord] = []
        self.root_tag: str = ""
        self.root_encoded: Any = None
        self.xml_decl: Dict[str, str] = {}

    def parse(self, data: bytes) -> Dict[str, Any]:
        p = expat.ParserCreate()
        # ordered_attributes=1 ⇒ attrs delivered as [name1, val1, name2, val2, ...]
        # in document order. This is the only way to get a stable attribute order.
        p.ordered_attributes = True
        # Coalesce adjacent character data into single callback fires.
        p.buffer_text = True
        p.StartElementHandler = self._on_start
        p.EndElementHandler = self._on_end
        p.CharacterDataHandler = self._on_chars
        p.StartCdataSectionHandler = self._on_start_cdata
        p.EndCdataSectionHandler = self._on_end_cdata
        p.XmlDeclHandler = self._on_xml_decl
        p.ProcessingInstructionHandler = self._on_pi
        p.StartDoctypeDeclHandler = self._on_doctype
        try:
            p.Parse(data, True)
        except expat.ExpatError as e:
            raise UnsupportedXmlError(f"XML parse error: {e}") from e

        result: Dict[str, Any] = {
            # _xml is always present with at least version+encoding in the
            # canonical form, even if the source omitted the declaration.
            # This makes the JSON a fix-point under round-trip translation.
            "_xml": self.xml_decl or {"version": "1.0", "encoding": "UTF-8"},
            self.root_tag: self.root_encoded,
        }
        return result

    # ----- expat handlers -----

    def _on_xml_decl(self, version, encoding, standalone):
        # standalone is intentionally dropped — the GNDS corpus does not use it
        # and expat's reporting of it is quirky. Add support if a real use case
        # appears.
        self.xml_decl = {
            "version": version if version is not None else "1.0",
            "encoding": encoding if encoding is not None else "UTF-8",
        }

    def _on_pi(self, target, data):
        raise UnsupportedXmlError(
            f"Processing instruction <?{target} ...?> is out of scope"
        )

    def _on_doctype(self, name, sysid, pubid, has_subset):
        raise UnsupportedXmlError(
            f"DOCTYPE declarations are out of scope (name={name!r})"
        )

    def _on_start(self, name: str, attrs_list) -> None:
        self._validate_name(name, kind="element")
        # attrs_list is [name1, val1, name2, val2, ...] thanks to ordered_attributes.
        attrs: Dict[str, str] = {}
        for i in range(0, len(attrs_list), 2):
            aname, aval = attrs_list[i], attrs_list[i + 1]
            if aname == "xmlns" or aname.startswith("xmlns:"):
                raise UnsupportedXmlError(
                    f"XML namespace declaration {aname!r} is out of scope"
                )
            self._validate_name(aname, kind="attribute")
            attrs[aname] = aval
        if self.stack:
            # Flush any text accumulated in the parent before this child.
            self.stack[-1].flush_text()
        self.stack.append(_ElementRecord(name, attrs))

    def _on_chars(self, data: str) -> None:
        if self.stack:
            self.stack[-1].pending_text += data

    def _on_start_cdata(self) -> None:
        if self.stack:
            self.stack[-1].set_cdata_state(True)

    def _on_end_cdata(self) -> None:
        if self.stack:
            self.stack[-1].set_cdata_state(False)

    def _on_end(self, _name: str) -> None:
        record = self.stack.pop()
        record.flush_text()
        encoded, is_cdata = self._encode(record)
        if not self.stack:
            self.root_tag = record.tag
            self.root_encoded = encoded
        else:
            self.stack[-1].add_elem(record.tag, encoded, is_cdata)

    # ----- encoding -----

    @staticmethod
    def _validate_name(name: str, kind: str) -> None:
        if name.startswith(ATTR_PREFIX):
            raise NameCollisionError(
                f"{kind.capitalize()} name {name!r} starts with reserved prefix "
                f"{ATTR_PREFIX!r}"
            )
        if name in RESERVED_META:
            raise NameCollisionError(
                f"{kind.capitalize()} name {name!r} collides with reserved meta key"
            )

    def _encode(self, record: _ElementRecord) -> Tuple[Any, bool]:
        """Apply spec §1 encoding rules to a finalized element record.

        Returns ``(encoded_value, self_is_cdata)``.  ``self_is_cdata`` is
        True iff the element's text content came entirely from CDATA
        sections; the caller (the parent) uses it to populate ``_cdata``.
        """
        elem_children = [
            payload for kind, payload in record.children if kind == "elem"
        ]
        plain_segments = [
            payload for kind, payload in record.children if kind == "text"
        ]
        cdata_segments = [
            payload for kind, payload in record.children if kind == "cdata_text"
        ]

        # Mixed-content check: element + non-whitespace text is forbidden by GNDS
        # and out of scope. Inter-element whitespace is silently dropped.
        if elem_children:
            for seg in plain_segments:
                if seg.strip():
                    raise MixedContentError(
                        f"Element <{record.tag}> contains both text content and "
                        "element children (mixed content is out of scope)"
                    )
            if cdata_segments:
                raise MixedContentError(
                    f"Element <{record.tag}> contains both CDATA text and element "
                    "children (mixed content is out of scope)"
                )
            plain_segments = []

        # Determine THIS element's text content and its CDATA-ness.
        text_combined, self_is_cdata = self._classify_text(
            record.tag, plain_segments, cdata_segments
        )

        # Bare-string shortcut: no attrs, no element children, no comments.
        if not record.attrs and not elem_children:
            return text_combined, self_is_cdata

        # Object form.
        result: Dict[str, Any] = {}
        for aname, aval in record.attrs.items():
            result[ATTR_PREFIX + aname] = aval

        # Group child elements by tag, preserving first-occurrence order.
        # Verify per-tag CDATA consistency along the way.
        grouped: Dict[str, list] = {}
        child_cdata_state: Dict[str, bool] = {}
        for tagname, val, child_is_cdata in elem_children:
            if tagname in child_cdata_state:
                if child_cdata_state[tagname] != child_is_cdata:
                    raise CdataInconsistencyError(
                        f"<{record.tag}>: child <{tagname}> has inconsistent "
                        "CDATA-ness across occurrences (some CDATA, some plain)"
                    )
            else:
                child_cdata_state[tagname] = child_is_cdata
            grouped.setdefault(tagname, []).append(val)
        for tagname, vals in grouped.items():
            result[tagname] = vals[0] if len(vals) == 1 else vals

        # Text alongside attributes (text+attrs case, spec §2 _text).
        if record.attrs and not elem_children and text_combined:
            result["_text"] = text_combined

        # _cdata: list of child tag names whose text was CDATA-encoded.
        cdata_tags = [t for t, was_cdata in child_cdata_state.items() if was_cdata]
        if cdata_tags:
            result["_cdata"] = cdata_tags

        return result, self_is_cdata

    @staticmethod
    def _classify_text(
        tag: str, plain_segments: List[str], cdata_segments: List[str]
    ) -> Tuple[str, bool]:
        """Combine text segments and decide whether the element's text is CDATA.

        - All-plain (or no text):       (combined, False)
        - All-CDATA (no plain segments): (combined, True)
        - Mixed (any plain AND any CDATA): error
        """
        has_plain = any(s for s in plain_segments)
        has_cdata = any(s for s in cdata_segments)
        if has_plain and has_cdata:
            raise CdataInconsistencyError(
                f"<{tag}>: text content mixes CDATA and plain text runs; "
                "this is not supported (would require segment-level CDATA tracking)"
            )
        if has_cdata:
            return "".join(cdata_segments), True
        return "".join(plain_segments), False
