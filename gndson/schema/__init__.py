"""
gndson.schema — schema-aware transformation library.

A collection of small, composable transformations that take the canonical
JSON form produced by the bottom-layer translator and rearrange it into
shapes that are more ergonomic for downstream consumers. Each transformation
is:

  - self-contained (carries name, summary, witnesses, examples, forward and
    inverse functions; see `gndson.schema.base.Transformation`),
  - testable in isolation (forward → inverse round-trip on the corpus),
  - composable into named `Pipeline`s applied in order.

The discipline is laid out in `framework.md`. The first-cut transformations
(arity enforcement, uniform-inner collapse, physicalQuantity wrapper
collapse, heterogeneous-inner collapse) are detailed in the
"First-cut schema-layer build order" section of that document.
"""

from .base import Pipeline, Transformation
from .arity import EnforceArrayArity, enforce_array_arity
from .inner_tag import DropUniformInnerTag, drop_uniform_inner_tag
from .physical_quantity import (
    AugmentKind,
    CollapsePhysicalQuantityWrappers,
    augment_kind,
    collapse_physicalQuantity_wrappers,
)
from .heterogeneous_inner_tag import (
    DropHeterogeneousInnerTag,
    drop_heterogeneous_inner_tag,
)
from .data_columns import ExpandDataColumns, expand_data_columns
from .docs import DOC_FIXTURE, render_all_markdown, render_markdown
from .pipelines import PIPELINES, get_pipeline, pipeline_names
from .whitespace_text import SplitWhitespaceText, split_whitespace_text

__all__ = [
    "Pipeline",
    "Transformation",
    "EnforceArrayArity",
    "enforce_array_arity",
    "DropUniformInnerTag",
    "drop_uniform_inner_tag",
    "AugmentKind",
    "CollapsePhysicalQuantityWrappers",
    "augment_kind",
    "collapse_physicalQuantity_wrappers",
    "DropHeterogeneousInnerTag",
    "drop_heterogeneous_inner_tag",
    "PIPELINES",
    "get_pipeline",
    "pipeline_names",
    "SplitWhitespaceText",
    "split_whitespace_text",
    "ExpandDataColumns",
    "expand_data_columns",
    "DOC_FIXTURE",
    "render_markdown",
    "render_all_markdown",
]
