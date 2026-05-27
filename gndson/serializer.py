"""
Canonical JSON dict -> XML, per spec.md.

Iteration 2c — supports everything before, plus:
  - _comments + _order: comments preserved at the right positions among siblings.
  - _text as list of strings: text split by comments inside text-only elements.

Earlier iterations:
  - 2b: _cdata
  - 1:  elements/attrs/text, bare-string and object forms, scalar-vs-list,
        _text for text+attrs, _xml, root-tag unwrap, entity escaping.

Not yet implemented:
  - _nocollapse, _attrorder.
"""

from typing import Any, Dict, FrozenSet, List, Tuple

from ._meta import RESERVED_META, ATTR_PREFIX
from .entities import EntityCodec, DEFAULT_CODEC
from .errors import MalformedJsonError


def write_xml_file(
    data: Dict[str, Any], path: str, *, codec: EntityCodec = DEFAULT_CODEC
) -> None:
    """Serialize a canonical-form dict to an XML file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_xml_string(data, codec=codec))


def to_xml_string(
    data: Dict[str, Any], *, codec: EntityCodec = DEFAULT_CODEC
) -> str:
    """Serialize a canonical-form dict to XML text."""
    if not isinstance(data, dict):
        raise MalformedJsonError("Top-level JSON must be an object (dict)")

    # XML declaration (§3).
    xml_decl = data.get("_xml", {})
    if not isinstance(xml_decl, dict):
        raise MalformedJsonError("_xml must be a JSON object")
    version = xml_decl.get("version", "1.0")
    encoding = xml_decl.get("encoding", "UTF-8")
    decl_line = f'<?xml version="{version}" encoding="{encoding}"?>\n'

    # Root tag: exactly one non-meta, non-attribute key (§3).
    candidates = [
        k for k in data
        if not k.startswith("_") and not k.startswith(ATTR_PREFIX)
    ]
    if len(candidates) != 1:
        raise MalformedJsonError(
            f"Top-level JSON must contain exactly one non-meta key (the root tag); "
            f"found {len(candidates)}: {candidates!r}"
        )
    root_tag = candidates[0]
    root_value = data[root_tag]

    body = _emit_element(root_tag, root_value, codec=codec)
    return decl_line + body


# ----- internal -----


def _emit_element(
    tag: str,
    value: Any,
    *,
    codec: EntityCodec,
    as_cdata: bool = False,
) -> str:
    """Emit a single XML element from its tag name and canonical-form value.

    ``as_cdata`` is supplied by the parent: if True, the element's text content
    is emitted inside ``<![CDATA[...]]>`` rather than entity-escaped. When the
    text is a list of segments (comment-split), every segment is CDATA-wrapped.
    """
    # Bare-string case: pure text content, no attrs, no children, no comments.
    if isinstance(value, str):
        if value == "":
            return f"<{tag}/>"
        body = _wrap_text(value, as_cdata=as_cdata, codec=codec)
        return f"<{tag}>{body}</{tag}>"

    if not isinstance(value, dict):
        raise MalformedJsonError(
            f"Element value for <{tag}> must be a string or object; "
            f"got {type(value).__name__}"
        )

    parts = _split_object(value, tag=tag)

    attr_str = "".join(
        f' {name}="{codec.encode_attr(val)}"' for name, val in parts.attrs
    )

    # Empty element: no children, no text content, no comments,
    # and either no _order or an empty _order.
    if (
        not parts.children
        and parts.text is None
        and not parts.comments
        and not parts.order  # None or empty list both OK
    ):
        return f"<{tag}{attr_str}/>"

    body = _emit_body(tag, parts, as_cdata=as_cdata, codec=codec)
    return f"<{tag}{attr_str}>{body}</{tag}>"


def _emit_body(
    tag: str, parts: "_Parts", *, as_cdata: bool, codec: EntityCodec
) -> str:
    """Emit the inner XML content of an element, honoring `_order` if present."""
    if parts.order is None:
        # No `_order`: emit text (if any), then children in JSON insertion order.
        # In this branch, there are no comments and `_text` is a string (or absent).
        out: List[str] = []
        if parts.text is not None:
            if not isinstance(parts.text, str):
                raise MalformedJsonError(
                    f"<{tag}>: _text must be a string when _order is absent"
                )
            out.append(_wrap_text(parts.text, as_cdata=as_cdata, codec=codec))
        for child_tag, child_val in parts.children:
            child_as_cdata = child_tag in parts.cdata_tags
            for v in _iter_child_values(child_val):
                out.append(_emit_element(child_tag, v, codec=codec, as_cdata=child_as_cdata))
        return "".join(out)

    # `_order` is present. Walk it, consuming from the per-source lists.
    out: List[str] = []
    text_idx = 0
    comment_idx = 0
    # Pre-index children for O(1) lookup.
    children_by_tag: Dict[str, list] = {}
    child_idx: Dict[str, int] = {}
    for child_tag, child_val in parts.children:
        children_by_tag[child_tag] = list(_iter_child_values(child_val))
        child_idx[child_tag] = 0

    # `_text` may be a string or a list. If it's a string, _order should not
    # contain any "_text" markers (the canonical form puts the string into
    # implicit position before any comments). We accept either shape but
    # validate consumption below.
    text_list = (
        parts.text if isinstance(parts.text, list)
        else ([parts.text] if isinstance(parts.text, str) else [])
    )

    for entry in parts.order:
        if entry == "_text":
            if text_idx >= len(text_list):
                raise MalformedJsonError(
                    f"<{tag}>: _order has more '_text' markers than _text entries"
                )
            out.append(_wrap_text(text_list[text_idx], as_cdata=as_cdata, codec=codec))
            text_idx += 1
        elif entry == "_comment":
            if comment_idx >= len(parts.comments):
                raise MalformedJsonError(
                    f"<{tag}>: _order has more '_comment' markers than _comments entries"
                )
            out.append(_emit_comment(parts.comments[comment_idx]))
            comment_idx += 1
        else:
            tag_name = entry
            if tag_name not in children_by_tag:
                raise MalformedJsonError(
                    f"<{tag}>: _order references unknown child tag {tag_name!r}"
                )
            idx = child_idx[tag_name]
            vals = children_by_tag[tag_name]
            if idx >= len(vals):
                raise MalformedJsonError(
                    f"<{tag}>: _order references more occurrences of <{tag_name}> "
                    "than exist in the JSON"
                )
            child_as_cdata = tag_name in parts.cdata_tags
            out.append(_emit_element(tag_name, vals[idx], codec=codec, as_cdata=child_as_cdata))
            child_idx[tag_name] = idx + 1

    # Consumption validation: everything must have been used exactly once.
    if text_idx != len(text_list):
        raise MalformedJsonError(
            f"<{tag}>: _order has fewer '_text' markers than _text entries"
        )
    if comment_idx != len(parts.comments):
        raise MalformedJsonError(
            f"<{tag}>: _order has fewer '_comment' markers than _comments entries"
        )
    for child_tag, vals in children_by_tag.items():
        if child_idx[child_tag] != len(vals):
            raise MalformedJsonError(
                f"<{tag}>: _order does not reference all occurrences of "
                f"<{child_tag}> ({child_idx[child_tag]} / {len(vals)})"
            )

    return "".join(out)


def _iter_child_values(child_val):
    """Yield child value(s) — flattening a JSON list (multi-occurrence form)
    and passing scalars through as a single-item iterable."""
    if isinstance(child_val, list):
        for v in child_val:
            yield v
    else:
        yield child_val


def _wrap_text(text: str, *, as_cdata: bool, codec: EntityCodec) -> str:
    if as_cdata:
        if "]]>" in text:
            raise MalformedJsonError(
                "CDATA-flagged text contains the forbidden sequence ']]>'"
            )
        return f"<![CDATA[{text}]]>"
    return codec.encode_text(text)


def _emit_comment(text: str) -> str:
    """Emit `<!--text-->`, validating that `text` doesn't violate XML comment rules."""
    if "--" in text:
        raise MalformedJsonError(
            f"comment text contains the forbidden substring '--': {text!r}"
        )
    if text.endswith("-"):
        raise MalformedJsonError(
            f"comment text ends with '-' (would produce '--->'): {text!r}"
        )
    return f"<!--{text}-->"


# Parsed object value — internal struct used by the emit functions.
class _Parts:
    __slots__ = ("attrs", "text", "children", "cdata_tags", "comments", "order")

    def __init__(self):
        self.attrs: List[Tuple[str, str]] = []
        self.text: Any = None
        self.children: List[Tuple[str, Any]] = []
        self.cdata_tags: FrozenSet[str] = frozenset()
        self.comments: List[str] = []
        self.order: List[str] = None  # None means "no _order key"


def _split_object(value: Dict[str, Any], *, tag: str) -> "_Parts":
    """Split an object-form value into the various parts used by the emitter."""
    parts = _Parts()
    for key, val in value.items():
        if key.startswith(ATTR_PREFIX):
            if not isinstance(val, str):
                raise MalformedJsonError(
                    f"<{tag}> attribute {key!r}: value must be a string, "
                    f"got {type(val).__name__}"
                )
            parts.attrs.append((key[len(ATTR_PREFIX):], val))
        elif key == "_text":
            if isinstance(val, str):
                parts.text = val
            elif isinstance(val, list) and all(isinstance(s, str) for s in val):
                parts.text = val
            else:
                raise MalformedJsonError(
                    f"<{tag}> _text must be a string or list of strings"
                )
        elif key == "_comments":
            if not isinstance(val, list) or not all(isinstance(c, str) for c in val):
                raise MalformedJsonError(
                    f"<{tag}> _comments must be a list of strings"
                )
            parts.comments = val
        elif key == "_order":
            if not isinstance(val, list) or not all(isinstance(e, str) for e in val):
                raise MalformedJsonError(
                    f"<{tag}> _order must be a list of strings"
                )
            parts.order = val
        elif key == "_cdata":
            if not isinstance(val, list) or not all(isinstance(t, str) for t in val):
                raise MalformedJsonError(
                    f"<{tag}> _cdata must be a list of strings"
                )
            parts.cdata_tags = frozenset(val)
        elif key in RESERVED_META:
            raise MalformedJsonError(
                f"<{tag}>: meta key {key!r} not yet supported in this iteration"
            )
        else:
            parts.children.append((key, val))
    return parts
