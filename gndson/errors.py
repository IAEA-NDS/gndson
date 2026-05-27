"""Exception hierarchy for gndson."""


class GndsonError(Exception):
    """Base class for all gndson errors."""


class UnsupportedXmlError(GndsonError):
    """An XML feature outside the translator's supported scope."""


class MixedContentError(UnsupportedXmlError):
    """Text content and element children mixed within the same element."""


class NameCollisionError(GndsonError):
    """An XML name (element or attribute) collides with translator-reserved prefixes/keys."""


class MalformedJsonError(GndsonError):
    """A JSON document violates the canonical-form rules of the spec."""


class CdataInconsistencyError(GndsonError):
    """Same-named children under one parent have inconsistent CDATA-ness."""
