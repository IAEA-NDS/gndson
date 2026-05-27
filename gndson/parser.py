"""
XML -> canonical JSON dict, per spec.md.

Iteration 2d — supports everything before, plus:
  - _nocollapse: track which empty children were written in pair form
    (`<x></x>`) rather than self-closing (`<x/>`).

Earlier iterations:
  - 2c: _comments, _order, _text-as-list (text split by comments)
  - 2b: _cdata
  - 1:  elements/attrs/text, bare-string shortcut, scalar-vs-list,
        _text for text+attrs, _xml declaration, root-tag wrap.

Note: _attrorder is supported on the SERIALIZER side only — the parser
does not emit it because JSON insertion order already preserves the
attribute order from the source XML.
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

    __slots__ = (
        "tag", "attrs", "children", "pending_text", "pending_is_cdata", "start_byte",
    )

    def __init__(self, tag: str, attrs: Dict[str, str], start_byte: int) -> None:
        self.tag = tag
        self.attrs = attrs
        # Children list of (kind, payload):
        #   ("text", str)                            — plain-text run
        #   ("cdata_text", str)                      — CDATA-section text run
        #   ("comment", str)                         — XML comment
        #   ("elem", (tagname, encoded_value, child_is_cdata, child_was_pair))
        self.children: List[Tuple[str, Any]] = []
        self.pending_text = ""
        self.pending_is_cdata = False
        # Byte offset of the start tag in the source — used to discriminate
        # self-closing (<x/>) from pair-form (<x></x>) empty elements.
        self.start_byte = start_byte

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

    def add_elem(
        self, tagname: str, value: Any, child_is_cdata: bool, child_was_pair: bool
    ) -> None:
        self.flush_text()
        self.children.append(
            ("elem", (tagname, value, child_is_cdata, child_was_pair))
        )


class _XmlToJson:
    """Expat-driven SAX handler that builds the canonical dict."""

    def __init__(self) -> None:
        self.stack: List[_ElementRecord] = []
        self.root_tag: str = ""
        self.root_encoded: Any = None
        self.xml_decl: Dict[str, str] = {}
        self._source: bytes = b""
        self._p: "expat.XMLParserType" = None  # set in parse()

    def parse(self, data: bytes) -> Dict[str, Any]:
        self._source = data
        p = expat.ParserCreate()
        self._p = p
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
        p.CommentHandler = self._on_comment
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
        self.stack.append(_ElementRecord(name, attrs, self._p.CurrentByteIndex))

    def _on_chars(self, data: str) -> None:
        if self.stack:
            self.stack[-1].pending_text += data

    def _on_start_cdata(self) -> None:
        if self.stack:
            self.stack[-1].set_cdata_state(True)

    def _on_end_cdata(self) -> None:
        if self.stack:
            self.stack[-1].set_cdata_state(False)

    def _on_comment(self, text: str) -> None:
        # Comments outside the root element are not preserved (spec §6).
        if not self.stack:
            return
        # A comment breaks the current text run.
        self.stack[-1].flush_text()
        self.stack[-1].children.append(("comment", text))

    def _on_end(self, _name: str) -> None:
        end_byte = self._p.CurrentByteIndex
        record = self.stack.pop()
        record.flush_text()
        encoded, is_cdata = self._encode(record)
        was_pair = self._was_pair_form(record, end_byte)
        if not self.stack:
            self.root_tag = record.tag
            self.root_encoded = encoded
        else:
            self.stack[-1].add_elem(record.tag, encoded, is_cdata, was_pair)

    def _was_pair_form(self, record: _ElementRecord, end_byte: int) -> bool:
        """Was this element written as <x></x> (pair form, empty body)?

        Only meaningful when the element is empty (no children, no text, no
        comments). Per spec §5 the two forms are equivalent; we record the
        choice only so the serializer can faithfully reproduce it when the
        user populates `_nocollapse`.
        """
        if record.children or record.pending_text:
            # Non-empty element; serializer never collapses to <x/> anyway.
            return False
        # bytes[start:end] is the opening tag's text. For self-closing it
        # ends with `/>`; for pair-form it ends with `>` (and an `</x>`
        # follows).
        slice_ = self._source[record.start_byte:end_byte]
        return slice_.endswith(b">") and not slice_.endswith(b"/>")

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
        has_elem = any(k == "elem" for k, _ in record.children)
        has_comment = any(k == "comment" for k, _ in record.children)
        plain_segments = [p for k, p in record.children if k == "text"]
        cdata_segments = [p for k, p in record.children if k == "cdata_text"]

        # Mixed-content check (text+element-children is forbidden by GNDS).
        if has_elem:
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

        # Classify the element's own text-CDATA-ness (only meaningful when
        # the element has no element children — otherwise its "text" is
        # just inter-tag whitespace).
        if has_elem:
            self_is_cdata = False
            text_combined = ""
        else:
            text_combined, self_is_cdata = self._classify_text(
                record.tag, plain_segments, cdata_segments
            )

        # Bare-string shortcut: no attrs, no element children, no comments.
        if not record.attrs and not has_elem and not has_comment:
            return text_combined, self_is_cdata

        # Object form. Walk children in document order, building parallel
        # structures: grouped element children, _order entries, _comments,
        # text segments (used only when text-only-with-comments).
        result: Dict[str, Any] = {}
        for aname, aval in record.attrs.items():
            result[ATTR_PREFIX + aname] = aval

        order_entries: List[str] = []
        comments_list: List[str] = []
        text_segments_in_order: List[str] = []
        grouped: Dict[str, list] = {}
        child_cdata_state: Dict[str, bool] = {}
        nocollapse_tags: List[str] = []  # tag-names with any pair-form empty child
        elem_tag_seq: List[str] = []

        for kind, payload in record.children:
            if kind == "elem":
                tagname, val, child_is_cdata, child_was_pair = payload
                if tagname in child_cdata_state:
                    if child_cdata_state[tagname] != child_is_cdata:
                        raise CdataInconsistencyError(
                            f"<{record.tag}>: child <{tagname}> has inconsistent "
                            "CDATA-ness across occurrences"
                        )
                else:
                    child_cdata_state[tagname] = child_is_cdata
                if child_was_pair and tagname not in nocollapse_tags:
                    nocollapse_tags.append(tagname)
                grouped.setdefault(tagname, []).append(val)
                order_entries.append(tagname)
                elem_tag_seq.append(tagname)
            elif kind == "comment":
                comments_list.append(payload)
                order_entries.append("_comment")
            elif kind in ("text", "cdata_text"):
                if has_elem:
                    # Already verified inter-tag whitespace; drop here.
                    continue
                # Text-only element: accumulate as a positional segment.
                # We always include the segment even if empty-string — the
                # parser only generates non-empty text runs (flush_text
                # skips empty pending_text), so payload is non-empty here.
                text_segments_in_order.append(payload)
                order_entries.append("_text")

        # Place grouped child elements into the result (insertion order
        # follows first-encounter of each tag).
        for tagname, vals in grouped.items():
            result[tagname] = vals[0] if len(vals) == 1 else vals

        # Text content placement.
        if has_elem:
            pass  # no text in container element
        elif has_comment:
            # Text-only with comments: always use list form so positions
            # are unambiguous (matched to "_text" markers in _order).
            if text_segments_in_order:
                result["_text"] = text_segments_in_order
        elif record.attrs:
            # Text + attrs, no children, no comments → string form.
            if text_combined:
                result["_text"] = text_combined

        # Meta keys (only when needed).
        if comments_list:
            result["_comments"] = comments_list

        cdata_tags = [t for t, was_cdata in child_cdata_state.items() if was_cdata]
        if cdata_tags:
            result["_cdata"] = cdata_tags

        if nocollapse_tags:
            result["_nocollapse"] = nocollapse_tags

        needs_order = has_comment or (
            has_elem and not _is_grouped(elem_tag_seq)
        )
        if needs_order:
            result["_order"] = order_entries

        return result, self_is_cdata

    @staticmethod
    def _classify_text(
        tag: str, plain_segments: List[str], cdata_segments: List[str]
    ) -> Tuple[str, bool]:
        """Combine text segments and decide whether the element's text is CDATA.

        - All-plain (or no text):        (combined, False)
        - All-CDATA (no plain segments): (combined, True)
        - Mixed (any plain AND any CDATA): error.
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


def _is_grouped(tag_sequence: List[str]) -> bool:
    """True iff each distinct tag in `tag_sequence` occurs as one consecutive run.

    [a, a, b, b]   -> True
    [a, b, a, b]   -> False (a returns after b)
    [a, b, b, a]   -> False
    [a, a, b, a]   -> False
    """
    seen = set()
    current = None
    for t in tag_sequence:
        if t == current:
            continue
        if t in seen:
            return False
        seen.add(t)
        current = t
    return True
