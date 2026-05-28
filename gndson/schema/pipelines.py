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
from .data_columns import expand_data_columns
from .heterogeneous_inner_tag import drop_heterogeneous_inner_tag
from .inner_tag import drop_uniform_inner_tag
from .physical_quantity import (
    augment_kind,
    collapse_physicalQuantity_wrappers,
)
from .whitespace_text import (
    TOKENIZED_NUMERIC_TAGS,
    split_whitespace_text,
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
    "split_text":    Pipeline([split_whitespace_text]),
    "data_columns":  Pipeline([expand_data_columns]),

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
    "ergonomic_split": Pipeline([
        enforce_array_arity,
        drop_uniform_inner_tag,
        augment_kind,
        collapse_physicalQuantity_wrappers,
        drop_heterogeneous_inner_tag,
        split_whitespace_text,
    ]),
    "ergonomic_split_data": Pipeline([
        enforce_array_arity,
        drop_uniform_inner_tag,
        augment_kind,
        collapse_physicalQuantity_wrappers,
        drop_heterogeneous_inner_tag,
        split_whitespace_text,
        expand_data_columns,
    ]),
}


# Pipelines that are bijective at the GNDS-spec level but NOT at the
# canonical-form byte level. The corpus driver compares the pre- and
# post-round-trip JSON after whitespace-normalising the listed tags in
# both, mirroring the spec-level notion of equivalence.
FUZZY_PIPELINES = {
    "split_text":           TOKENIZED_NUMERIC_TAGS,
    "ergonomic_split":      TOKENIZED_NUMERIC_TAGS,
    "ergonomic_split_data": TOKENIZED_NUMERIC_TAGS,
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


def fuzzy_tags_for(name: str):
    """Return the set of tag names whose text content should be
    whitespace-normalised when comparing the inputs and outputs of a
    round-trip through pipeline `name`, or `None` if the pipeline is
    bijective at the canonical-form byte level."""
    return FUZZY_PIPELINES.get(name)


def normalise_for_fuzzy_compare(data, tags):
    """Return a deep copy of `data` with whitespace-normalised text bodies
    for elements whose tag is in `tags`. Handles three canonical shapes:

      bare string:   {tag: "  1\\n  2  "} -> {tag: "1 2"}
      object form:   {tag: {"@a": "x", "_text": "1\\n  2"}}
                       -> {tag: {"@a": "x", "_text": "1 2"}}
      list of either: each item gets the appropriate normalisation.

    Used by the CLI's `verify --pipeline` and by the schema corpus
    driver to compare pre- and post-round-trip JSON when the pipeline
    is bijective at the GNDS-spec level but not at the canonical-form
    byte level (i.e. listed in `FUZZY_PIPELINES`)."""
    from copy import deepcopy
    out = deepcopy(data)
    _walk_normalise(out, tags, tag=None)
    return out


def _walk_normalise(data, tags, tag=None):
    if not isinstance(data, dict):
        return
    # If this node is itself a tokenised element (object form), normalise
    # its `_text` value.
    if tag in tags:
        text = data.get("_text")
        if isinstance(text, str):
            data["_text"] = " ".join(text.split())
    # Process tokenised children of this node.
    for k, v in list(data.items()):
        if k.startswith("@") or k.startswith("_"):
            continue
        if k in tags:
            if isinstance(v, str):
                data[k] = " ".join(v.split())
            elif isinstance(v, list):
                data[k] = [
                    " ".join(item.split()) if isinstance(item, str) else item
                    for item in v
                ]
        # Recurse with tag context.
        child = data[k]
        if isinstance(child, dict):
            _walk_normalise(child, tags, tag=k)
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    _walk_normalise(item, tags, tag=k)
