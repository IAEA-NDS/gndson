"""
Transformation: collapse the redundant inner tag of uniform plural containers.

For each parent element in `UNIFORM_PLURAL_CONTAINERS`, if the container
holds ONLY the expected inner tag (no comments, no attributes, no other
children), collapse the redundant inner key:

    {Xs: {X: [obj1, obj2]}}   ->   {Xs: [obj1, obj2]}
    {Xs: {X: scalar}}         ->   {Xs: [scalar]}
    {Xs: {}}                  ->   {Xs: []}

Inverse: re-wrap the list under the inner tag taken from the same
dictionary, restoring `{Xs: {X: list}}`.

When the container has interleaved comments, attributes, or unexpected
extra children, the collapse is skipped — the canonical form is preserved
unchanged so the round-trip stays identity. This means downstream output
shape is mostly-but-not-uniformly collapsed; that is intentional, because
the alternative is silently dropping comments.

Pipeline note: this transformation is designed to follow
`enforce_array_arity` in the canonical pipeline (`[arity, inner_tag]`).
Used standalone on canonical JSON it does not round-trip exactly because
the inverse always emits a list under the inner key and the canonical
form uses a scalar when there is a single child. The composition
`[arity, inner_tag]` does round-trip exactly because arity already
normalises to always-list.

See framework.md §"First-cut schema-layer build order" / step 2.
"""

from __future__ import annotations
from copy import deepcopy
from typing import Any, Callable

from .arity import UNIFORM_PLURAL_CONTAINERS
from .base import Transformation


class DropUniformInnerTag(Transformation):
    name = "drop_uniform_inner_tag"
    summary = (
        "Collapse plural containers with one known inner tag: "
        "{Xs: {X: [list]}} -> {Xs: [list]}. Skipped when the container "
        "has comments or other meta keys."
    )
    witnesses_added = ()
    witnesses_consumed = ()
    example_before = {
        "reactions": {"reaction": [{"@label": "a"}, {"@label": "b"}]},
        "products":  {"product":  []},
    }
    example_after = {
        "reactions": [{"@label": "a"}, {"@label": "b"}],
        "products":  [],
    }

    def forward(self, data: Any) -> Any:
        return _walk(deepcopy(data), _collapse)

    def inverse(self, data: Any) -> Any:
        return _walk(deepcopy(data), _expand)


# ----- internal -----


def _collapse(node: dict) -> None:
    """For each plural-container child key in `node` whose value is a dict
    containing ONLY the expected inner tag, collapse to a bare list."""
    for k, v in list(node.items()):
        if k.startswith("@") or k.startswith("_"):
            continue
        if k not in UNIFORM_PLURAL_CONTAINERS:
            continue
        if not isinstance(v, dict):
            continue  # already collapsed (list) or otherwise non-dict
        inner = UNIFORM_PLURAL_CONTAINERS[k]
        # Skip collapse if anything else lives in v (attrs, meta keys,
        # unexpected sibling tags). The container's structure must be
        # preserved so comments etc. don't get lost.
        extras = [kk for kk in v if kk != inner]
        if extras:
            continue
        if inner in v:
            inner_val = v[inner]
            node[k] = inner_val if isinstance(inner_val, list) else [inner_val]
        else:
            node[k] = []


def _expand(node: dict) -> None:
    """Inverse of `_collapse`: re-wrap a bare list under the expected
    inner tag for known plural containers."""
    for k, v in list(node.items()):
        if k.startswith("@") or k.startswith("_"):
            continue
        if k not in UNIFORM_PLURAL_CONTAINERS:
            continue
        if not isinstance(v, list):
            continue
        inner = UNIFORM_PLURAL_CONTAINERS[k]
        node[k] = {inner: v}


def _walk(data: Any, visit: Callable[[dict], None]) -> Any:
    """Top-down walker. Calls `visit(node)` on each dict node before
    recursing into its children. Modifications happen in-place; the same
    root is returned."""
    if isinstance(data, dict):
        visit(data)
        for k, v in list(data.items()):
            if k.startswith("@") or k.startswith("_"):
                continue
            if isinstance(v, dict):
                _walk(v, visit)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        _walk(item, visit)
    return data


# Singleton instance for use in pipelines.
drop_uniform_inner_tag = DropUniformInnerTag()
