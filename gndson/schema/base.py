"""
Base class for schema-layer transformations, and the Pipeline that composes
them.

A `Transformation` declares its identity (name, summary), the witnesses it
introduces and consumes, and small before/after examples that double as
testable fixtures. Subclasses implement `_forward_inplace(data)` and
`_inverse_inplace(data)` — both contracts are "mutate the input tree in
place; the same root reference is logically returned".

Callers use the public `forward(data, *, inplace=False)` and
`inverse(data, *, inplace=False)` methods. By default the base class
deep-copies the input before handing it to the subclass's in-place body,
so ad-hoc callers do not accidentally clobber their data. Power callers
who already own a fresh copy (most importantly, `Pipeline` after its
single up-front copy) can pass `inplace=True` to skip the copy entirely.

A `Pipeline` is an ordered list of transformations. `pipeline.forward`
applies them left-to-right; `pipeline.inverse` applies them right-to-
left — the natural inverse for a composition. Pipeline performs ONE
deep-copy up front (unless the caller opts out) and then drives every
transformation in `inplace=True` mode, so the total cost of an
N-transformation pipeline is one copy regardless of N.

See framework.md (sections "Transformation library and auto-documentation"
and "First-cut schema-layer build order") for the discipline.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, List, Sequence


class Transformation(ABC):
    """A single schema-layer transformation. Subclasses must set the
    class-level metadata and implement `_forward_inplace` /
    `_inverse_inplace`. The public `forward` / `inverse` methods handle
    the deep-copy bookkeeping so the in-place implementations stay
    short."""

    name: str = ""
    summary: str = ""
    witnesses_added: Sequence[str] = ()
    witnesses_consumed: Sequence[str] = ()
    example_before: Any = None
    example_after: Any = None

    def forward(self, data: Any, *, inplace: bool = False) -> Any:
        """Apply the transformation.

        If `inplace=False` (default), the input tree is deep-copied first;
        the caller's data is untouched. If `inplace=True`, the input is
        mutated and returned; the caller must not assume the original
        reference is preserved structurally."""
        if not inplace:
            data = deepcopy(data)
        self._forward_inplace(data)
        return data

    def inverse(self, data: Any, *, inplace: bool = False) -> Any:
        """Undo the transformation. Same `inplace` semantics as `forward`."""
        if not inplace:
            data = deepcopy(data)
        self._inverse_inplace(data)
        return data

    @abstractmethod
    def _forward_inplace(self, data: Any) -> None:
        """Mutate `data` in place to apply the forward transformation."""

    @abstractmethod
    def _inverse_inplace(self, data: Any) -> None:
        """Mutate `data` in place to apply the inverse transformation."""

    def __repr__(self) -> str:  # pragma: no cover — cosmetic
        return f"<Transformation {self.name!r}>"


class Pipeline:
    """An ordered list of transformations applied left-to-right by `forward`
    and right-to-left by `inverse`.

    Performs ONE deep-copy of the input (unless `inplace=True` is passed)
    and then drives every constituent transformation in in-place mode,
    so the deep-copy cost is O(1) in the number of transformations rather
    than O(N).
    """

    def __init__(self, transformations: List[Transformation]) -> None:
        self.transformations = list(transformations)

    def forward(self, data: Any, *, inplace: bool = False) -> Any:
        if not inplace:
            data = deepcopy(data)
        for t in self.transformations:
            t.forward(data, inplace=True)
        return data

    def inverse(self, data: Any, *, inplace: bool = False) -> Any:
        if not inplace:
            data = deepcopy(data)
        for t in reversed(self.transformations):
            t.inverse(data, inplace=True)
        return data

    def __repr__(self) -> str:  # pragma: no cover — cosmetic
        names = ", ".join(t.name for t in self.transformations)
        return f"<Pipeline [{names}]>"
