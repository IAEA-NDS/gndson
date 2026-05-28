"""
gndson: round-trip translation between GNDS XML and JSON.

See spec.md for the canonical-form definition.
"""

from .parser import parse_xml_file, parse_xml_bytes
from .serializer import write_xml_file, to_xml_string
from .entities import EntityCodec, DEFAULT_CODEC
from .errors import (
    GndsonError,
    UnsupportedXmlError,
    MixedContentError,
    NameCollisionError,
    MalformedJsonError,
    CdataInconsistencyError,
)

__all__ = [
    "parse_xml_file",
    "parse_xml_bytes",
    "write_xml_file",
    "to_xml_string",
    "EntityCodec",
    "DEFAULT_CODEC",
    "GndsonError",
    "UnsupportedXmlError",
    "MixedContentError",
    "NameCollisionError",
    "MalformedJsonError",
    "CdataInconsistencyError",
]

__version__ = "0.1.0a1"
