"""
Transformation: expand <data> element header comments into structured
columns and rows.

In FUDGE-generated GNDS files, <data> elements often carry a comment
that names the columns of the tabular body:

    <data>
      <!-- energy | L | J | totalWidth | neutronWidth | captureWidth -->
           -10740   0   0.5  102.6217   101.7507  0.871
           ...
    </data>

This is a FUDGE output convention — it is NOT part of the GNDS 2.1
spec — so the transformation lives apart from the strict spec-driven
transformations and is opt-in. It is also a HEURISTIC: the forward
only augments <data> elements whose first comment looks like a
pipe-separated header AND whose text body tokenises evenly by the
column count. Non-matching elements are left untouched.

Forward augments matching <data> dicts with:

    _columns: list of column-name strings (parsed from the first comment).
    _rows:    list of rows, each a list of cell strings (parsed from
              the text body, whitespace-tokenised and grouped in
              column-count chunks).

The original _text, _comments, and _order are preserved unchanged —
they act as the witness for the augmentation. Inverse simply strips
_columns and _rows. Bijective at the byte level: this is a clean
augmentation in the framework sense, not a reduction.

Corpus survey (at module-author time): 212 / 212 of the <data>
elements in the bundled GNDS corpus match this heuristic, including
the 147 / 212 that have multiple comments (multi-line headers — we
use the first comment, which is the primary header; secondary
comments stay in _comments unchanged).
"""

from __future__ import annotations
from typing import Any, Callable, Optional

from .base import Transformation


# The single tag this transformation operates on.
DATA_TAG = "data"

# Column separator used in FUDGE-style header comments.
HEADER_SEPARATOR = "|"


class ExpandDataColumns(Transformation):
    name = "expand_data_columns"
    summary = (
        "Heuristic augmentation: parse <data> elements' pipe-separated "
        "header comments into _columns and group the text body into "
        "_rows (list of lists of token strings)."
    )
    witnesses_added = ("_columns", "_rows")
    witnesses_consumed = ()
    example_before = {
        "data": {
            "_text": ["\n  ", "\n  1 2 3\n  4 5 6\n"],
            "_comments": ["a | b | c"],
            "_order": ["_text", "_comment", "_text"],
        }
    }
    example_after = {
        "data": {
            "_text": ["\n  ", "\n  1 2 3\n  4 5 6\n"],
            "_comments": ["a | b | c"],
            "_order": ["_text", "_comment", "_text"],
            "_columns": ["a", "b", "c"],
            "_rows": [["1", "2", "3"], ["4", "5", "6"]],
        }
    }

    def _forward_inplace(self, data: Any) -> None:
        _walk(data, _expand)

    def _inverse_inplace(self, data: Any) -> None:
        _walk(data, _strip)


# ----- internal -----


def _expand(node: dict, tag: Optional[str]) -> None:
    """For a <data> element matching the FUDGE header-comment convention,
    add _columns and _rows. Skip everything else."""
    if tag != DATA_TAG:
        return
    if "_columns" in node or "_rows" in node:
        return  # already augmented; preserve idempotence
    comments = node.get("_comments")
    if not isinstance(comments, list) or not comments:
        return  # need at least one comment as the header
    header = comments[0]
    if not isinstance(header, str) or HEADER_SEPARATOR not in header:
        return  # not a pipe-separated header
    columns = [c.strip() for c in header.split(HEADER_SEPARATOR)]
    if len(columns) < 2 or any(not c for c in columns):
        return  # need >=2 non-empty column names
    text = node.get("_text")
    if text is None:
        return
    if isinstance(text, str):
        body = text
    elif isinstance(text, list):
        body = "".join(t for t in text if isinstance(t, str))
    else:
        return
    tokens = body.split()
    if not tokens:
        return
    n = len(columns)
    if len(tokens) % n != 0:
        return  # heuristic doesn't fit — leave alone
    rows = [tokens[i:i + n] for i in range(0, len(tokens), n)]
    node["_columns"] = columns
    node["_rows"] = rows


def _strip(node: dict, tag: Optional[str]) -> None:
    """Inverse: remove the augmentation keys from any node."""
    node.pop("_columns", None)
    node.pop("_rows", None)


def _walk(data: Any, visit: Callable[[dict, Optional[str]], None],
          tag: Optional[str] = None) -> Any:
    """Top-down walker; passes tag context like other schema-layer walkers."""
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
expand_data_columns = ExpandDataColumns()
