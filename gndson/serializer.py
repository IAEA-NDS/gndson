"""
Canonical JSON dict -> XML, per spec.md.

Iteration 2 — supports everything in iteration 1, plus:
  - _cdata: emit listed child tags' text inside <![CDATA[...]]>.

Iteration 1 baseline:
  - Elements, attributes, text content
  - Top-level root-tag unwrapping (spec §3)
  - Bare-string and object element forms (§1)
  - Scalar and list child values (§1)
  - _text key as a string (§2)
  - _xml declaration metadata (§3)
  - Entity escaping in text and attribute values (§8)

Not yet implemented:
  - _comments / _order, _nocollapse, _text-as-list, _attrorder.
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
    is emitted inside ``<![CDATA[...]]>`` rather than entity-escaped.
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

    attrs, text, children, child_cdata_tags = _split_object(value, tag=tag)

    attr_str = "".join(
        f' {name}="{codec.encode_attr(val)}"' for name, val in attrs
    )

    # Empty element: no children, no text content.
    if not children and text is None:
        return f"<{tag}{attr_str}/>"

    inner_parts: List[str] = []
    if text is not None:
        inner_parts.append(_wrap_text(text, as_cdata=as_cdata, codec=codec))
    for child_tag, child_val in children:
        child_as_cdata = child_tag in child_cdata_tags
        if isinstance(child_val, list):
            for v in child_val:
                inner_parts.append(
                    _emit_element(child_tag, v, codec=codec, as_cdata=child_as_cdata)
                )
        else:
            inner_parts.append(
                _emit_element(child_tag, child_val, codec=codec, as_cdata=child_as_cdata)
            )

    return f"<{tag}{attr_str}>{''.join(inner_parts)}</{tag}>"


def _wrap_text(text: str, *, as_cdata: bool, codec: EntityCodec) -> str:
    if as_cdata:
        if "]]>" in text:
            raise MalformedJsonError(
                "CDATA-flagged text contains the forbidden sequence ']]>'"
            )
        return f"<![CDATA[{text}]]>"
    return codec.encode_text(text)


def _split_object(
    value: Dict[str, Any], *, tag: str
) -> Tuple[List[Tuple[str, str]], Any, List[Tuple[str, Any]], FrozenSet[str]]:
    """Split an object-form value into (attrs, text, children, cdata_tags) parts."""
    attrs: List[Tuple[str, str]] = []
    text: Any = None
    children: List[Tuple[str, Any]] = []
    cdata_tags: FrozenSet[str] = frozenset()
    for key, val in value.items():
        if key.startswith(ATTR_PREFIX):
            if not isinstance(val, str):
                raise MalformedJsonError(
                    f"<{tag}> attribute {key!r}: value must be a string, "
                    f"got {type(val).__name__}"
                )
            attrs.append((key[len(ATTR_PREFIX):], val))
        elif key == "_text":
            if not isinstance(val, str):
                # List form (text split by comments) is a later iteration.
                raise MalformedJsonError(
                    f"<{tag}> _text must be a string in this iteration "
                    "(list form not yet supported)"
                )
            text = val
        elif key == "_cdata":
            if not isinstance(val, list) or not all(isinstance(t, str) for t in val):
                raise MalformedJsonError(
                    f"<{tag}> _cdata must be a list of strings"
                )
            cdata_tags = frozenset(val)
        elif key in RESERVED_META:
            raise MalformedJsonError(
                f"<{tag}>: meta key {key!r} not yet supported in this iteration"
            )
        else:
            children.append((key, val))
    return attrs, text, children, cdata_tags
