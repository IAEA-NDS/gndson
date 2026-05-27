"""
Entity codec for the 5 XML predefined entities: & < > " '

Used only on the WRITE side. On the read side, the expat parser delivers
character data already entity-decoded.

The default codec escapes minimally — only characters that would be
syntactically invalid in their context. Subclass or replace `EntityCodec`
to swap in a different policy without touching the parser/serializer.
"""


class EntityCodec:
    """Default minimal entity encoder."""

    # In element text, & and < must be escaped. > is also escaped to avoid
    # producing the CDATA-end sequence ']]>'.
    _TEXT_TABLE = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})

    # Inside double-quoted attribute values, additionally escape ".
    _ATTR_TABLE = str.maketrans({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
    })

    def encode_text(self, s: str) -> str:
        """Escape characters that are invalid in XML element text."""
        return s.translate(self._TEXT_TABLE)

    def encode_attr(self, s: str) -> str:
        """Escape characters that are invalid in a double-quoted attribute value."""
        return s.translate(self._ATTR_TABLE)


DEFAULT_CODEC = EntityCodec()
