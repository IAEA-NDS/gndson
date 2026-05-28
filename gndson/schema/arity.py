"""
Transformation: enforce always-list discipline for plural containers.

For each parent element listed in `UNIFORM_PLURAL_CONTAINERS`, the named
inner child key is always a JSON list:

  - a scalar gets wrapped in a 1-element list,
  - an absent inner key gets an empty list `[]`,
  - an existing list stays as-is.

The inverse restores the canonical form: a 1-element list becomes a
scalar, an empty list removes the key.

No JSON-level witness is required — the curated dictionary is the source
of truth at both forward and inverse time. See framework.md
§"First-cut schema-layer build order" / step 1 for the rationale.

Heterogeneous-inner containers (e.g. `function1ds`, `styles`, `distribution`,
`sums`) are intentionally absent from this dictionary; they will be
handled by a later transformation in conjunction with the `_kind`
witness.
"""

from __future__ import annotations
from copy import deepcopy
from typing import Any, Callable, Optional

from .base import Transformation


# Curated map: plural-container tag → uniform inner tag.
# Source: GNDS 2.1 spec (cross-checked against the corpus).
UNIFORM_PLURAL_CONTAINERS = {
    "reactions":         "reaction",
    "products":          "product",
    "axes":              "axis",
    "aliases":           "alias",
    "baryons":           "baryon",
    "gaugeBosons":       "gaugeBoson",
    "nuclides":          "nuclide",
    "chemicalElements":  "chemicalElement",
    "isotopes":          "isotope",
}


class EnforceArrayArity(Transformation):
    name = "enforce_array_arity"
    summary = (
        "For known plural containers, ensure the named inner child is "
        "always a JSON list (wrap scalars, insert [] when absent)."
    )
    witnesses_added = ()
    witnesses_consumed = ()
    example_before = {
        "reactions": {"reaction": {"@label": "n + H1"}},
        "products":  {},
    }
    example_after = {
        "reactions": {"reaction": [{"@label": "n + H1"}]},
        "products":  {"product":  []},
    }

    def forward(self, data: Any) -> Any:
        return _walk(deepcopy(data), _enforce)

    def inverse(self, data: Any) -> Any:
        return _walk(deepcopy(data), _restore)


# ----- internal -----


def _enforce(node: dict, tag: Optional[str]) -> None:
    """If `node` represents a known plural container, ensure its inner
    child is a list (wrap scalars, insert [] when absent)."""
    if tag not in UNIFORM_PLURAL_CONTAINERS:
        return
    inner = UNIFORM_PLURAL_CONTAINERS[tag]
    if inner in node:
        v = node[inner]
        if not isinstance(v, list):
            node[inner] = [v]
    else:
        node[inner] = []


def _restore(node: dict, tag: Optional[str]) -> None:
    """Inverse of `_enforce`: de-listify 1-element lists, drop empty ones."""
    if tag not in UNIFORM_PLURAL_CONTAINERS:
        return
    inner = UNIFORM_PLURAL_CONTAINERS[tag]
    if inner in node:
        v = node[inner]
        if isinstance(v, list):
            if len(v) == 0:
                del node[inner]
            elif len(v) == 1:
                node[inner] = v[0]


def _walk(data: Any, visitor: Callable[[dict, Optional[str]], None],
          tag: Optional[str] = None) -> Any:
    """Recursively walk the canonical-form data.

    `visitor(node, tag)` is invoked on each dict node, where `tag` is the
    XML tag-name under which the node sits in its parent (or None at the
    document root). Modifications happen in-place; the same root is
    returned for chaining.
    """
    if isinstance(data, dict):
        visitor(data, tag)
        # Snapshot the items before iterating, since the visitor may add
        # keys (the [] insertion when the inner child is absent).
        for k, v in list(data.items()):
            if k.startswith("@") or k.startswith("_"):
                continue
            if isinstance(v, dict):
                _walk(v, visitor, k)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        _walk(item, visitor, k)
    return data


# Singleton instance for use in pipelines.
enforce_array_arity = EnforceArrayArity()
