"""Reserved-name constants shared by parser and serializer."""

# Reserved meta keys (per spec §2, §3, §4). All start with `_`.
RESERVED_META = frozenset({
    "_order", "_attrorder", "_text", "_comments",
    "_cdata", "_nocollapse", "_xml", "_comment",
})

# Reserved attribute-key prefix.
ATTR_PREFIX = "@"
