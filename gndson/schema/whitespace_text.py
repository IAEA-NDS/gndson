"""
Transformation: split whitespace-tokenised text into JSON lists.

For each element whose tag is in `TOKENIZED_NUMERIC_TAGS`, the body
(text content) is split on runs of whitespace and stored as a JSON
list of token strings. The inverse re-joins tokens with single spaces.

Three canonical input shapes are handled symmetrically:

  (A) Single occurrence, bare-string form (the most common case):
      canonical:  "values": "1.0 2.0 3.0"
      forward:    "values": ["1.0", "2.0", "3.0"]            # flat list

  (B) Single occurrence, object form (when the element has attrs such as
      `start` / `length`, GNDS §5.2.1):
      canonical:  "values": {"@start": "0", "_text": "1.0 2.0"}
      forward:    "values": {"@start": "0", "_text": ["1.0", "2.0"]}

  (C) Multi-occurrence (one parent holds several <values> siblings;
      each may be bare-string or object form independently):
      canonical:  "values": ["a b", {"@start": "5", "_text": "c d"}]
      forward:    "values": [["a", "b"], {"@start": "5", "_text": ["c", "d"]}]
                  # nested list — the inverse uses this nesting to
                  # distinguish multi-occurrence post-forward from
                  # single-occurrence post-forward.

Disambiguation: single-occurrence post-forward is a flat list of strings;
multi-occurrence post-forward is a list whose items are themselves lists
or dicts. The inverse switches on this shape distinction.

Round-trip semantics:

- **Bijective at the GNDS-spec level.** Per spec §5.2.1, the body of
  `<values>` is "a list of whitespace-separated values"; internal
  whitespace carries no information.
- **NOT bijective at the canonical-form byte level.** A source body of
  ``"1\\n  2\\n  3"`` becomes ``"1 2 3"`` after a forward + inverse
  cycle. The schema corpus driver handles this via a fuzzy comparator
  (see `gndson.schema.pipelines.FUZZY_PIPELINES`) that
  whitespace-normalises the tokenised tags before comparing.

The dictionary of "tags whose text is whitespace-tokenised" is schema
knowledge; that's what places this transformation in the schema layer.
"""

from __future__ import annotations
from typing import Any, Callable, Optional

from .base import Transformation


# Tags whose text body is a whitespace-tokenised list per the GNDS spec.
# Currently scoped to `<values>` (the most common case). `<grid>` and
# `<data>` in `sep="whiteSpace"` mode are natural extensions; defer until
# corpus-driven evidence shows they're needed.
TOKENIZED_NUMERIC_TAGS = frozenset({
    "values",
})


class SplitWhitespaceText(Transformation):
    name = "split_whitespace_text"
    summary = (
        "Split text-only elements whose body is a whitespace-separated "
        "list into JSON lists of token strings. Bijective at the "
        "GNDS-spec level (internal whitespace is normalised)."
    )
    witnesses_added = ()
    witnesses_consumed = ()
    example_before = {"values": "1.0 2.0 3.0"}
    example_after = {"values": ["1.0", "2.0", "3.0"]}

    def _forward_inplace(self, data: Any) -> None:
        _walk(data, _split)

    def _inverse_inplace(self, data: Any) -> None:
        _walk(data, _join)


# ----- internal -----


def _split(node: dict, tag: Optional[str]) -> None:
    """Forward visitor: handle both bare-string-child case (A/C) and
    own-element object-form case (B)."""
    # Case A / C: tokenised children of this node.
    for k, v in list(node.items()):
        if k.startswith("@") or k.startswith("_"):
            continue
        if k not in TOKENIZED_NUMERIC_TAGS:
            continue
        if isinstance(v, str):
            # (A) Single-occurrence bare string → flat list of tokens.
            node[k] = v.split()
        elif isinstance(v, list):
            # (C) Multi-occurrence: each string item becomes a list of
            # tokens; dict items are left alone (the walker will recurse
            # into them and Case B handles each).
            node[k] = [
                item.split() if isinstance(item, str) else item
                for item in v
            ]
    # Case B: this node IS a tokenised element in object form. The walker
    # arrived here either by recursing into a single-occurrence dict child
    # or by recursing into a dict item of a multi-occurrence list.
    if tag in TOKENIZED_NUMERIC_TAGS:
        text = node.get("_text")
        if isinstance(text, str):
            node["_text"] = text.split()


def _join(node: dict, tag: Optional[str]) -> None:
    """Inverse visitor: mirror of `_split`. Distinguishes single-
    occurrence post-forward (flat list of strings) from multi-occurrence
    post-forward (list of lists / dicts)."""
    # Inverse of Case A / C.
    for k, v in list(node.items()):
        if k.startswith("@") or k.startswith("_"):
            continue
        if k not in TOKENIZED_NUMERIC_TAGS:
            continue
        if not isinstance(v, list):
            continue
        if all(isinstance(t, str) for t in v):
            # (A) Flat list of token strings → single-occurrence canonical.
            node[k] = " ".join(v)
        else:
            # (C) Multi-occurrence post-forward: each item must be either
            # a list-of-tokens (was a bare-string item) or a dict (was an
            # object-form item; walker rejoins its _text via Case B).
            # Anything else is malformed input.
            new_items = []
            for item in v:
                if isinstance(item, list) and all(isinstance(t, str) for t in item):
                    new_items.append(" ".join(item))
                elif isinstance(item, dict):
                    new_items.append(item)
                else:
                    raise ValueError(
                        f"<{k}>: post-forward list item must be a dict or a "
                        f"list of strings, got {type(item).__name__}"
                    )
            node[k] = new_items
    # Inverse of Case B.
    if tag in TOKENIZED_NUMERIC_TAGS:
        text = node.get("_text")
        if isinstance(text, list):
            if not all(isinstance(t, str) for t in text):
                raise ValueError(
                    f"<{tag}>: _text list contains non-string elements: "
                    f"{sorted({type(t).__name__ for t in text})}"
                )
            node["_text"] = " ".join(text)


def _walk(data: Any, visit: Callable[[dict, Optional[str]], None],
          tag: Optional[str] = None) -> Any:
    """Top-down walker. Calls `visit(node, tag)` on each dict node where
    `tag` is the XML tag-name under which the node sits in its parent."""
    if isinstance(data, dict):
        visit(data, tag)
        for k, v in list(data.items()):
            if k.startswith("@") or k.startswith("_"):
                continue
            if isinstance(v, dict):
                _walk(v, visit, k)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        _walk(item, visit, k)
    return data


# Singleton instance for use in pipelines.
split_whitespace_text = SplitWhitespaceText()
