"""
Named schema-layer pipelines.

A pipeline is an ordered list of schema transformations. This module
defines the canonical names used by the CLI (`gndson xml-to-json
--pipeline NAME`), by the corpus test driver, and by any other tool
that wants a stable identifier for a particular shape of post-canonical
JSON.

The names are intentionally short; the underlying transformations are
imported from their respective modules. Add a new entry here when a
new named pipeline becomes worth promoting to the public API.

See `framework.md` §"First-cut schema-layer build order" for the
rationale behind the individual transformations and the recommended
composition.
"""

from __future__ import annotations

from .arity import enforce_array_arity
from .base import Pipeline
from .heterogeneous_inner_tag import drop_heterogeneous_inner_tag
from .inner_tag import drop_uniform_inner_tag
from .physical_quantity import (
    augment_kind,
    collapse_physicalQuantity_wrappers,
)


PIPELINES = {
    # Identity pipeline. Explicit name for "no schema transformation".
    "canonical": Pipeline([]),

    # Single-step pipelines, one per transformation, for fine control.
    "arity":         Pipeline([enforce_array_arity]),
    "uniform":       Pipeline([enforce_array_arity, drop_uniform_inner_tag]),
    "wrappers":      Pipeline([augment_kind,
                               collapse_physicalQuantity_wrappers]),
    "heterogeneous": Pipeline([drop_heterogeneous_inner_tag]),

    # Recommended end-user pipelines.
    "ergonomic": Pipeline([
        enforce_array_arity,
        drop_uniform_inner_tag,
        augment_kind,
        collapse_physicalQuantity_wrappers,
    ]),
    "ergonomic_full": Pipeline([
        enforce_array_arity,
        drop_uniform_inner_tag,
        augment_kind,
        collapse_physicalQuantity_wrappers,
        drop_heterogeneous_inner_tag,
    ]),
}


def pipeline_names():
    """Return the list of available pipeline names, in declaration order."""
    return list(PIPELINES.keys())


def get_pipeline(name: str) -> Pipeline:
    """Look up a named pipeline. Raises ``KeyError`` if not found."""
    try:
        return PIPELINES[name]
    except KeyError:
        known = ", ".join(PIPELINES.keys())
        raise KeyError(
            f"unknown pipeline {name!r}; available: {known}"
        ) from None
