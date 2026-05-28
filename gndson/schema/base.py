"""
Base class for schema-layer transformations, and the Pipeline that composes
them.

A `Transformation` declares its identity (name, summary), the witnesses it
introduces and consumes, and small before/after examples that double as
testable fixtures. It implements `forward(data) -> data` and
`inverse(data) -> data`, both operating on the canonical JSON form (a
nested Python dict / list / str tree).

A `Pipeline` is an ordered list of transformations. `pipeline.forward`
applies them in order; `pipeline.inverse` applies them in reverse order
— the natural inverse for a composition.

See framework.md (sections "Transformation library and auto-documentation"
and "First-cut schema-layer build order") for the discipline.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, List, Sequence


class Transformation(ABC):
    """A single schema-layer transformation. Subclasses must set the
    class-level metadata and implement `forward` and `inverse`."""

    name: str = ""
    summary: str = ""
    witnesses_added: Sequence[str] = ()
    witnesses_consumed: Sequence[str] = ()
    example_before: Any = None
    example_after: Any = None

    @abstractmethod
    def forward(self, data: Any) -> Any:
        """Apply the transformation. Must return a new value (not mutate input)."""

    @abstractmethod
    def inverse(self, data: Any) -> Any:
        """Undo the transformation. Must return a new value (not mutate input)."""

    def __repr__(self) -> str:  # pragma: no cover — cosmetic
        return f"<Transformation {self.name!r}>"


class Pipeline:
    """An ordered list of transformations applied left-to-right by `forward`
    and right-to-left by `inverse`."""

    def __init__(self, transformations: List[Transformation]) -> None:
        self.transformations = list(transformations)

    def forward(self, data: Any) -> Any:
        for t in self.transformations:
            data = t.forward(data)
        return data

    def inverse(self, data: Any) -> Any:
        for t in reversed(self.transformations):
            data = t.inverse(data)
        return data

    def __repr__(self) -> str:  # pragma: no cover — cosmetic
        names = ", ".join(t.name for t in self.transformations)
        return f"<Pipeline [{names}]>"
