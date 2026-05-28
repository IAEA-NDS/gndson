"""
Transformation: collapse heterogeneous-inner plural containers.

For each parent element in `HETEROGENEOUS_PLURAL_CONTAINERS`, the
container's mixed-type children are reorganised as a flat JSON list with
each item carrying `_kind: <original-inner-tag>`:

    {function1ds: {XYs1d: [a, b], regions1d: c}}

becomes

    {function1ds: [
        {_kind: "XYs1d", ...a},
        {_kind: "XYs1d", ...b},
        {_kind: "regions1d", ...c},
    ]}

Inverse: walk the flat list, group items by `_kind`, restore the
`{kind: scalar-or-list}` dict shape using the canonical count-driven
rule (one item → scalar; two or more → list).

When the container itself has meta keys (`_order` / `_comments`) or
attributes, the collapse is skipped to preserve those edge cases
unchanged (mirrors the rule from `drop_uniform_inner_tag`). Containers
whose items are bare strings also block collapse, since there is no
obvious place to attach `_kind` on a string.

This transformation reuses the `_kind` witness mechanism introduced by
`augment_kind` / `collapse_physicalQuantity_wrappers` (step 3) but is
independent of them — the physicalQuantityNode wrapper set and the
heterogeneous-plural-container set do not overlap.

See framework.md §"First-cut schema-layer build order" / step 4.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List

from .base import Transformation


# Curated set of heterogeneous-plural-container tag names.
# Each entry is a parent element that holds zero or more children of
# one of several allowed inner tag names; the collapse flattens to a
# single list with each item annotated by `_kind`.
#
# Sources: corpus inspection (axes, aliases discovered in step-2 dictionary
# audit) cross-checked against GNDS 2.1 spec §5.1.1 (axes), §12.1.2 (aliases),
# §16.1.1 / 17.3.1 (function1ds inner-type list), and the spec entries for
# styles, sums, function2ds.
HETEROGENEOUS_PLURAL_CONTAINERS = frozenset({
    "function1ds",
    "function2ds",
    "styles",
    "axes",
    "aliases",
    "sums",
})


class DropHeterogeneousInnerTag(Transformation):
    name = "drop_heterogeneous_inner_tag"
    summary = (
        "Collapse heterogeneous-inner plural containers to a flat list "
        "of items, each annotated with _kind: <original-inner-tag>."
    )
    witnesses_added = ("_kind",)
    witnesses_consumed = ()
    example_before = {
        "function1ds": {
            "XYs1d":     [{"@index": "0"}, {"@index": "1"}],
            "regions1d": {"@a": "x"},
        }
    }
    example_after = {
        "function1ds": [
            {"_kind": "XYs1d",     "@index": "0"},
            {"_kind": "XYs1d",     "@index": "1"},
            {"_kind": "regions1d", "@a":     "x"},
        ]
    }

    def _forward_inplace(self, data: Any) -> None:
        _walk(data, _collapse)

    def _inverse_inplace(self, data: Any) -> None:
        _walk(data, _expand)


# ----- internal -----


def _collapse(parent: dict) -> None:
    """For each heterogeneous-plural-container child key of `parent`,
    collapse `{inner_tag: scalar_or_list, ...}` to a flat list whose
    items carry `_kind`."""
    for k, v in list(parent.items()):
        if k.startswith("@") or k.startswith("_"):
            continue
        if k not in HETEROGENEOUS_PLURAL_CONTAINERS:
            continue
        if not isinstance(v, dict):
            continue  # already collapsed (list) or otherwise non-dict
        # Skip if the container has meta or attribute keys (we'd lose them).
        if any(kk.startswith("@") or kk.startswith("_") for kk in v):
            continue
        # Skip if any inner item is a bare string — no place for _kind.
        if not _all_items_are_dicts(v):
            continue
        flat: List[dict] = []
        for inner_tag, inner_val in v.items():
            items = inner_val if isinstance(inner_val, list) else [inner_val]
            for item in items:
                new_item = dict(item)
                new_item["_kind"] = inner_tag
                flat.append(new_item)
        parent[k] = flat


def _expand(parent: dict) -> None:
    """Inverse of `_collapse`: for each heterogeneous-plural-container
    child key whose value is a flat list, re-group items by `_kind`
    back into a `{kind: scalar-or-list}` dict, restoring the canonical
    count-driven encoding."""
    for k, v in list(parent.items()):
        if k.startswith("@") or k.startswith("_"):
            continue
        if k not in HETEROGENEOUS_PLURAL_CONTAINERS:
            continue
        if not isinstance(v, list):
            continue
        grouped: Dict[str, list] = {}
        for item in v:
            if not isinstance(item, dict) or "_kind" not in item:
                raise ValueError(
                    f"<{k}>: item in collapsed list lacks _kind: {item!r}"
                )
            kind = item["_kind"]
            stripped = {kk: vv for kk, vv in item.items() if kk != "_kind"}
            grouped.setdefault(kind, []).append(stripped)
        result: dict = {}
        for kind, items in grouped.items():
            result[kind] = items[0] if len(items) == 1 else items
        parent[k] = result


def _all_items_are_dicts(container: dict) -> bool:
    """True iff every value in `container` is either a dict or a list of dicts."""
    for v in container.values():
        if isinstance(v, list):
            if any(not isinstance(it, dict) for it in v):
                return False
        elif not isinstance(v, dict):
            return False
    return True


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
drop_heterogeneous_inner_tag = DropHeterogeneousInnerTag()
