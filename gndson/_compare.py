"""
Strict XML-equivalence comparator for round-trip testing.

Two comparison levels are available, both implemented as parses into a
faithful in-memory tree compared with ``==``:

  - **Spec-equivalence** (``strict_form=False``, default). Preserves tag
    names, attributes (order-ignored), child order, comments, text
    byte-exact, and CDATA-ness. Per spec §9, ignores: inter-tag
    whitespace, self-closing-vs-pair form, attribute order, attribute
    quote character, minimal entity escaping.

  - **Byte-form-strict** (``strict_form=True``). All of the above PLUS
    the self-closing-vs-pair distinction. This is the level at which
    ``_nocollapse`` is verified to round-trip correctly. Attribute order
    is still ignored (use ``_attrorder`` to enforce it on the JSON side).

The strict mode is a superset: every pair that passes strict also passes
spec-equivalence. The two levels are reported separately so the corpus
driver can distinguish "spec round-trip broken" from "spec round-trip
fine but byte-form fidelity lost".
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
    # Self-closing form indicator. Only set meaningfully when strict_form=True
    # is passed to parse_faithful AND the element is empty (no body content).
    # In non-strict mode it is left at the constant default so equality is
    # unaffected by the source-syntax difference.
    self_closing: bool = False


@dataclass
class Comment:
    text: str


@dataclass
class Text:
    text: str
    is_cdata: bool


Node = Union[Element, Comment, Text]


def parse_faithful(data: bytes, *, strict_form: bool = False) -> Element:
    """Parse XML bytes into a faithful tree, post-processed to drop inter-tag whitespace.

    When ``strict_form=True``, each empty element's ``self_closing`` field is
    populated from the source bytes (True for ``<x/>``, False for ``<x></x>``);
    in the default mode the field is left at its constant default so that the
    two source forms compare equal.
    """
    p = expat.ParserCreate()
    p.ordered_attributes = True
    p.buffer_text = True

    stack: List[Element] = []
    root_container: List[Element] = []  # 1-list trick to allow inner assignment
    in_cdata = [False]
    elem_start_byte: Dict[int, int] = {}  # id(elem) -> start byte

    def on_start(name, attrs_list):
        attrs = {attrs_list[i]: attrs_list[i + 1] for i in range(0, len(attrs_list), 2)}
        elem = Element(tag=name, attrs=attrs)
        if strict_form:
            elem_start_byte[id(elem)] = p.CurrentByteIndex
        if stack:
            stack[-1].children.append(elem)
        else:
            root_container.append(elem)
        stack.append(elem)

    def on_end(_name):
        elem = stack[-1]
        if strict_form and not elem.children:
            start = elem_start_byte.pop(id(elem), None)
            if start is not None:
                end = p.CurrentByteIndex
                slice_ = data[start:end]
                elem.self_closing = slice_.endswith(b"/>")
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
    if a.self_closing != b.self_closing:
        form_a = "self-closing <{}/>".format(a.tag) if a.self_closing else f"pair-form <{a.tag}></{a.tag}>"
        form_b = "self-closing <{}/>".format(b.tag) if b.self_closing else f"pair-form <{b.tag}></{b.tag}>"
        return f"{path}<{a.tag}>: form differs ({form_a} vs {form_b})"
    if len(a.children) != len(b.children):
        return (f"{path}<{a.tag}>: child count differs "
                f"({len(a.children)} vs {len(b.children)})")
    for i, (ca, cb) in enumerate(zip(a.children, b.children)):
        sub_path = f"{path}{a.tag}[{i}]/"
        d = diff_summary(ca, cb, sub_path)
        if d:
            return d
    return ""
