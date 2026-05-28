"""
Transformations for GNDS physicalQuantityNode wrappers.

Two transformations form the canonical augment-then-collapse chain:

  augment_kind
    For each element whose tag is a known physicalQuantity wrapper
    (`mass`, `charge`, `spin`, `parity`, `halflife`, `energy`, `Q`,
    `probability`) and which has exactly one element child (no attributes,
    no meta keys, no other content), annotate it with `_kind: <inner-tag>`.
    Pure augmentation. Inverse strips `_kind`.

  collapse_physicalQuantity_wrappers
    For each element carrying `_kind` and a matching inner child, hoist
    the child's attributes and sub-children onto the wrapper, then drop
    the inner key. The inverse re-creates the inner child by gathering
    everything except `_kind`. `_kind` remains in the end-state JSON.

Wrappers that do not meet the eligibility rules (multi-child
style-labelled alternates, heterogeneous typed children, attributes on
the wrapper itself) are left untouched by augment_kind, and therefore
also untouched by collapse_physicalQuantity_wrappers — the canonical
form passes through unchanged.

See framework.md §"First-cut schema-layer build order" / step 3.
"""

from __future__ import annotations
from typing import Any, Callable, Optional

from .base import Transformation


# Tags formally declared `physicalQuantityNode` in GNDS 2.1.
# Sources: §2.3.3 (the abstract type); §11.3 / Table 11.1 (PoPs particle
# properties: mass, charge, spin, parity, halflife, energy); §13.1
# (reaction-data: mass, energy); §17.1.2 (Q); §13.3.1 (probability).
PHYSICAL_QUANTITY_WRAPPERS = frozenset({
    "mass",
    "charge",
    "spin",
    "parity",
    "halflife",
    "energy",
    "Q",
    "probability",
})


class AugmentKind(Transformation):
    name = "augment_kind"
    summary = (
        "For each physicalQuantityNode wrapper with exactly one element "
        "child (no attributes, no meta keys), annotate it with "
        "_kind: <inner-tag>."
    )
    witnesses_added = ("_kind",)
    witnesses_consumed = ()
    example_before = {
        "mass": {"double": {"@label": "eval", "@value": "1.0", "@unit": "amu"}}
    }
    example_after = {
        "mass": {
            "_kind": "double",
            "double": {"@label": "eval", "@value": "1.0", "@unit": "amu"},
        }
    }

    def _forward_inplace(self, data: Any) -> None:
        _walk(data, _annotate)

    def _inverse_inplace(self, data: Any) -> None:
        _walk(data, _strip_kind)


class CollapsePhysicalQuantityWrappers(Transformation):
    name = "collapse_physicalQuantity_wrappers"
    summary = (
        "For each element carrying _kind, hoist the matching inner "
        "child's attributes and sub-children onto the wrapper; the "
        "inverse re-creates the inner child using _kind."
    )
    # _kind is READ but not removed — it persists in the end-state JSON
    # as the witness that lets the inverse rebuild the inner child.
    witnesses_added = ()
    witnesses_consumed = ()
    example_before = {
        "mass": {
            "_kind": "double",
            "double": {"@label": "eval", "@value": "1.0", "@unit": "amu"},
        }
    }
    example_after = {
        "mass": {
            "_kind": "double",
            "@label": "eval",
            "@value": "1.0",
            "@unit": "amu",
        }
    }

    def _forward_inplace(self, data: Any) -> None:
        _walk(data, _hoist)

    def _inverse_inplace(self, data: Any) -> None:
        _walk(data, _unhoist)


# ----- internal -----


def _annotate(node: dict, tag: Optional[str]) -> None:
    """If `node` is a collapsible physicalQuantity wrapper, add `_kind`."""
    if tag not in PHYSICAL_QUANTITY_WRAPPERS:
        return
    # Skip if any attribute or meta key is already present. This rules out
    # wrappers with stray attributes (forbidden by spec but tolerated as a
    # safety) and wrappers carrying meta like _comments / _order.
    if any(k.startswith("@") or k.startswith("_") for k in node):
        return
    # Eligible only if there is exactly one element child whose value is a
    # dict. Multi-occurrence (list-valued inner) is the style-labelled
    # alternates case; multi-tag (more than one key) is the heterogeneous
    # case (e.g. charge with both integer and fraction); a string value is
    # a bare-string empty element. None of these are collapsible.
    items = list(node.items())
    if len(items) != 1:
        return
    inner_tag, inner_val = items[0]
    if not isinstance(inner_val, dict):
        return
    node["_kind"] = inner_tag


def _strip_kind(node: dict, tag: Optional[str]) -> None:
    """Remove the `_kind` annotation wherever it appears.

    Tag-name unaware: anywhere `_kind` appears it was added by
    augment_kind (the reserved-prefix rules guarantee no user-data
    collision)."""
    if "_kind" in node:
        del node["_kind"]


def _hoist(node: dict, tag: Optional[str]) -> None:
    """If `node` has `_kind` and a matching inner child, hoist the
    child's contents onto the wrapper and drop the inner key."""
    kind = node.get("_kind")
    if kind is None:
        return
    if kind not in node:
        return  # already hoisted, or no matching inner
    inner = node[kind]
    if not isinstance(inner, dict):
        return  # safety: only collapse if inner is a dict
    # Detect collision: an inner key that already exists on the wrapper
    # (and is not the inner's own tag).
    for k in inner:
        if k in node and k != kind:
            raise ValueError(
                f"hoist conflict: <{tag or '?'}>._kind={kind!r} would "
                f"overwrite existing key {k!r} on the wrapper"
            )
    for k, v in inner.items():
        node[k] = v
    del node[kind]


def _unhoist(node: dict, tag: Optional[str]) -> None:
    """Inverse of `_hoist`: if `_kind` is present without a matching
    inner child, gather everything else into a new inner of that name."""
    kind = node.get("_kind")
    if kind is None:
        return
    if kind in node:
        return  # already in pre-hoist (augmented but un-collapsed) form
    inner: dict = {}
    for k, v in list(node.items()):
        if k == "_kind":
            continue
        inner[k] = v
        del node[k]
    node[kind] = inner


def _walk(data: Any, visit: Callable[[dict, Optional[str]], None],
          tag: Optional[str] = None) -> Any:
    """Top-down walker. Calls `visit(node, tag)` on each dict node before
    recursing into its children. `tag` is the XML tag-name of the node
    (its key in the parent), or None at the document root."""
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


# Singleton instances for use in pipelines.
augment_kind = AugmentKind()
collapse_physicalQuantity_wrappers = CollapsePhysicalQuantityWrappers()
