"""
XML -> canonical JSON dict, per spec.md.

Iteration 1 (walking skeleton) — supports:
  - Elements, attributes, text content (incl. attribute order)
  - Top-level root-tag wrapping (spec §3)
  - Bare-string shortcut for text-only-no-attr-no-children elements (§1)
  - Object form with @-prefixed attributes (§1)
  - Scalar-vs-list child encoding by count (§1)
  - _text key for text alongside attributes (§2; reserved case B1)
  - _xml declaration metadata (§3)

Not yet implemented (planned for later iterations):
  - _cdata (CDATA section detection on read)
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

    __slots__ = ("tag", "attrs", "children", "pending_text")

    def __init__(self, tag: str, attrs: Dict[str, str]) -> None:
        self.tag = tag
        self.attrs = attrs
        # Children list of (kind, payload):
        #   ("text", str)
        #   ("elem", (tagname, encoded_value))
        # Later iterations add: ("comment", str), ("cdata_text", str).
        self.children: List[Tuple[str, Any]] = []
        self.pending_text = ""

    def flush_text(self) -> None:
        if self.pending_text:
            self.children.append(("text", self.pending_text))
            self.pending_text = ""

    def add_elem(self, tagname: str, value: Any) -> None:
        self.flush_text()
        self.children.append(("elem", (tagname, value)))


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

    def _on_end(self, _name: str) -> None:
        record = self.stack.pop()
        record.flush_text()
        encoded = self._encode(record)
        if not self.stack:
            self.root_tag = record.tag
            self.root_encoded = encoded
        else:
            self.stack[-1].add_elem(record.tag, encoded)

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

    def _encode(self, record: _ElementRecord) -> Any:
        """Apply spec §1 encoding rules to a finalized element record."""
        elem_children = [payload for kind, payload in record.children if kind == "elem"]
        text_segments = [payload for kind, payload in record.children if kind == "text"]

        # Mixed-content check: element + non-whitespace text is forbidden by GNDS
        # and out of scope for this translator. Inter-element whitespace is dropped.
        if elem_children:
            for seg in text_segments:
                if seg.strip():
                    raise MixedContentError(
                        f"Element <{record.tag}> contains both text content and "
                        "element children (mixed content is out of scope)"
                    )
            text_segments = []  # all whitespace; discard

        # Bare-string shortcut: no attrs, no element children (and no comments,
        # which aren't preserved yet in this iteration).
        if not record.attrs and not elem_children:
            return "".join(text_segments)

        # Object form.
        result: Dict[str, Any] = {}
        for aname, aval in record.attrs.items():
            result[ATTR_PREFIX + aname] = aval

        # Group child elements by tag, preserving first-occurrence order.
        grouped: Dict[str, list] = {}
        for tagname, val in elem_children:
            grouped.setdefault(tagname, []).append(val)
        for tagname, vals in grouped.items():
            result[tagname] = vals[0] if len(vals) == 1 else vals

        # Text alongside attributes (text+attrs case, spec §2 _text). Per the
        # corpus this is empty in current GNDS, but we support it (option B1).
        if record.attrs and not elem_children:
            combined = "".join(text_segments)
            if combined:
                result["_text"] = combined

        return result
