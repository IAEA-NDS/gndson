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

__all__ = [
    "Pipeline",
    "Transformation",
    "EnforceArrayArity",
    "enforce_array_arity",
    "DropUniformInnerTag",
    "drop_uniform_inner_tag",
]
