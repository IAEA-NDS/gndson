"""
Strict XML-equivalence comparator for round-trip testing.

Parses an XML document into a faithful in-memory tree that preserves:
  - Element tag names and attributes (attribute order ignored)
  - Child element order
  - XML comments (text and position among siblings)
  - Text content byte-exact (newlines, indentation, leading/trailing ws)
  - CDATA-ness of text content

Two trees compare equal iff their XMLs are equivalent per spec §9.
Differences in inter-tag whitespace, self-closing-vs-pair form, attribute
order, attribute quote character, and minimal entity escaping are ignored.

This is the honest yardstick for the round-trip property: a lossy parser
cannot game it by being equally lossy on both sides.
"""

from __future__ import annotations

import xml.parsers.expat as expat
from dataclasses import dataclass, field
from typing import Dict, List, Union


@dataclass
class Element:
    tag: str
    # Plain dict; equality ignores key order (Python semantics).
    attrs: Dict[str, str] = field(default_factory=dict)
    children: List["Node"] = field(default_factory=list)


@dataclass
class Comment:
    text: str


@dataclass
class Text:
    text: str
    is_cdata: bool


Node = Union[Element, Comment, Text]


def parse_faithful(data: bytes) -> Element:
    """Parse XML bytes into a faithful tree, post-processed to drop inter-tag whitespace."""
    p = expat.ParserCreate()
    p.ordered_attributes = True
    p.buffer_text = True

    stack: List[Element] = []
    root_container: List[Element] = []  # 1-list trick to allow inner assignment
    in_cdata = [False]

    def on_start(name, attrs_list):
        attrs = {attrs_list[i]: attrs_list[i + 1] for i in range(0, len(attrs_list), 2)}
        elem = Element(tag=name, attrs=attrs)
        if stack:
            stack[-1].children.append(elem)
        else:
            root_container.append(elem)
        stack.append(elem)

    def on_end(_name):
        stack.pop()

    def on_chars(text):
        if not stack:
            return
        parent = stack[-1]
        is_cdata_now = in_cdata[0]
        # Coalesce with prior text node of identical cdata-ness.
        if (parent.children
                and isinstance(parent.children[-1], Text)
                and parent.children[-1].is_cdata == is_cdata_now):
            parent.children[-1].text += text
        else:
            parent.children.append(Text(text=text, is_cdata=is_cdata_now))

    def on_comment(text):
        if stack:
            stack[-1].children.append(Comment(text=text))

    def on_start_cdata():
        in_cdata[0] = True

    def on_end_cdata():
        in_cdata[0] = False

    p.StartElementHandler = on_start
    p.EndElementHandler = on_end
    p.CharacterDataHandler = on_chars
    p.CommentHandler = on_comment
    p.StartCdataSectionHandler = on_start_cdata
    p.EndCdataSectionHandler = on_end_cdata
    p.Parse(data, True)

    if not root_container:
        raise ValueError("XML document had no root element")
    root = root_container[0]
    _drop_inter_tag_whitespace(root)
    return root


def _drop_inter_tag_whitespace(elem: Element) -> None:
    """Recursively remove whitespace-only plain-text nodes from container elements.

    Rule (per spec §5):
      - If an element has any element children, plain-text-non-cdata children
        that are whitespace-only are inter-tag whitespace -> drop.
      - Otherwise (leaf-text element, possibly with comments interleaving the
        text, possibly with CDATA) all text is preserved byte-exact.
    """
    has_element_children = any(isinstance(c, Element) for c in elem.children)
    if has_element_children:
        elem.children = [
            c for c in elem.children
            if not (isinstance(c, Text) and not c.is_cdata and not c.text.strip())
        ]
    for child in elem.children:
        if isinstance(child, Element):
            _drop_inter_tag_whitespace(child)


def diff_summary(a: Element, b: Element, path: str = "/") -> str:
    """Return a short human-readable description of the first difference, or ''.

    Used for failure messages — comparing two big GNDS trees with `assert a == b`
    gives an unreadable dump; this walks until it finds a difference.
    """
    if type(a) is not type(b):
        return f"{path}: node type {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, Comment):
        if a.text != b.text:
            return f"{path}: comment text differs: {a.text!r} vs {b.text!r}"
        return ""
    if isinstance(a, Text):
        if a.is_cdata != b.is_cdata:
            return f"{path}: text cdata-ness differs ({a.is_cdata} vs {b.is_cdata})"
        if a.text != b.text:
            return f"{path}: text differs: {a.text!r} vs {b.text!r}"
        return ""
    # Element
    if a.tag != b.tag:
        return f"{path}: tag differs: {a.tag!r} vs {b.tag!r}"
    if a.attrs != b.attrs:
        only_a = set(a.attrs) - set(b.attrs)
        only_b = set(b.attrs) - set(a.attrs)
        diff_vals = {k: (a.attrs[k], b.attrs[k])
                     for k in a.attrs if k in b.attrs and a.attrs[k] != b.attrs[k]}
        return (f"{path}<{a.tag}>: attrs differ "
                f"(only_a={sorted(only_a)}, only_b={sorted(only_b)}, "
                f"vals={diff_vals})")
    if len(a.children) != len(b.children):
        return (f"{path}<{a.tag}>: child count differs "
                f"({len(a.children)} vs {len(b.children)})")
    for i, (ca, cb) in enumerate(zip(a.children, b.children)):
        sub_path = f"{path}{a.tag}[{i}]/"
        d = diff_summary(ca, cb, sub_path)
        if d:
            return d
    return ""
