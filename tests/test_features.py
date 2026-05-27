"""Unit tests for spec rules — small handcrafted cases per rule."""

import pytest

from gndson import (
    parse_xml_bytes, to_xml_string,
    MixedContentError, NameCollisionError, MalformedJsonError,
    UnsupportedXmlError, CdataInconsistencyError,
)


# ===== Parser: XML -> JSON =====

class TestParser:
    def test_simple_text_child_bare_string(self):
        result = parse_xml_bytes(b'<?xml version="1.0" encoding="UTF-8"?><r><x>hello</x></r>')
        assert result == {
            "_xml": {"version": "1.0", "encoding": "UTF-8"},
            "r": {"x": "hello"},
        }

    def test_empty_root_bare_string(self):
        result = parse_xml_bytes(b'<r/>')
        # _xml is always present in canonical form, defaulted when source omits the decl.
        assert result == {"_xml": {"version": "1.0", "encoding": "UTF-8"}, "r": ""}

    def test_attributes_object_form(self):
        result = parse_xml_bytes(b'<r><x a="1" b="2"/></r>')
        assert result["r"] == {"x": {"@a": "1", "@b": "2"}}

    def test_attribute_order_preserved(self):
        result = parse_xml_bytes(b'<r a="1" b="2" c="3"/>')
        assert list(result["r"].keys()) == ["@a", "@b", "@c"]

    def test_scalar_when_single_child(self):
        result = parse_xml_bytes(b'<r><x>1</x></r>')
        assert result["r"] == {"x": "1"}

    def test_list_when_two_children(self):
        result = parse_xml_bytes(b'<r><x>1</x><x>2</x></r>')
        assert result["r"] == {"x": ["1", "2"]}

    def test_list_preserves_order(self):
        result = parse_xml_bytes(b'<r><x>a</x><x>b</x><x>c</x></r>')
        assert result["r"]["x"] == ["a", "b", "c"]

    def test_nested_elements(self):
        result = parse_xml_bytes(b'<r><a><b><c>x</c></b></a></r>')
        assert result["r"] == {"a": {"b": {"c": "x"}}}

    def test_inter_tag_whitespace_dropped(self):
        result = parse_xml_bytes(b'<r>\n  <x>1</x>\n  <x>2</x>\n</r>')
        assert result["r"] == {"x": ["1", "2"]}

    def test_text_alongside_attrs_uses_text_key(self):
        result = parse_xml_bytes(b'<r><x a="1">hello</x></r>')
        assert result["r"] == {"x": {"@a": "1", "_text": "hello"}}

    def test_mixed_content_rejected(self):
        with pytest.raises(MixedContentError):
            parse_xml_bytes(b'<r>text<x/></r>')

    def test_doctype_rejected(self):
        with pytest.raises(UnsupportedXmlError):
            parse_xml_bytes(b'<!DOCTYPE r><r/>')

    def test_namespace_decl_rejected(self):
        with pytest.raises(UnsupportedXmlError):
            parse_xml_bytes(b'<r xmlns="http://example.com"/>')

    def test_processing_instruction_rejected(self):
        with pytest.raises(UnsupportedXmlError):
            parse_xml_bytes(b'<?xml-stylesheet href="x.css"?><r/>')

    def test_reserved_attr_name_rejected(self):
        with pytest.raises(NameCollisionError):
            parse_xml_bytes(b'<r><x _order="1"/></r>')

    def test_reserved_tag_name_rejected(self):
        with pytest.raises(NameCollisionError):
            parse_xml_bytes(b'<r><_xml/></r>')

    def test_at_prefix_attr_name_rejected(self):
        # NOTE: this depends on expat tolerating @ in attribute names.
        # If expat rejects the XML itself first, this becomes an UnsupportedXmlError,
        # which is also acceptable.
        with pytest.raises((NameCollisionError, UnsupportedXmlError)):
            parse_xml_bytes(b'<r @attr="1"/>')


# ===== Serializer: JSON -> XML =====

class TestSerializer:
    def test_simple_root_with_text_child(self):
        data = {"r": {"x": "hello"}}
        xml = to_xml_string(data)
        assert xml == '<?xml version="1.0" encoding="UTF-8"?>\n<r><x>hello</x></r>'

    def test_empty_root_self_closing(self):
        assert to_xml_string({"r": ""}) == '<?xml version="1.0" encoding="UTF-8"?>\n<r/>'

    def test_attributes_quoted_in_order(self):
        xml = to_xml_string({"r": {"x": {"@a": "1", "@b": "2"}}})
        assert '<x a="1" b="2"/>' in xml

    def test_xml_decl_preserved(self):
        xml = to_xml_string({"_xml": {"version": "1.0", "encoding": "UTF-8"}, "r": ""})
        assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    def test_list_child_emits_repeated_elements(self):
        xml = to_xml_string({"r": {"x": ["1", "2", "3"]}})
        assert '<x>1</x><x>2</x><x>3</x>' in xml

    def test_text_attr_via_text_key(self):
        xml = to_xml_string({"r": {"x": {"@a": "1", "_text": "hello"}}})
        assert '<x a="1">hello</x>' in xml

    def test_entity_escape_in_text(self):
        xml = to_xml_string({"r": {"x": "a < b & c > d"}})
        assert "&amp;" in xml and "&lt;" in xml and "&gt;" in xml

    def test_entity_escape_in_attr(self):
        xml = to_xml_string({"r": {"x": {"@a": 'has "quote"'}}})
        assert '&quot;' in xml

    def test_zero_root_keys_rejected(self):
        with pytest.raises(MalformedJsonError):
            to_xml_string({"_xml": {}})

    def test_multiple_root_keys_rejected(self):
        with pytest.raises(MalformedJsonError):
            to_xml_string({"a": {}, "b": {}})

    def test_unsupported_meta_key_rejected(self):
        # _order etc. not yet supported in this iteration; _cdata IS supported.
        with pytest.raises(MalformedJsonError):
            to_xml_string({"r": {"_order": ["x"], "x": ""}})


# ===== Synthetic round-trip cases (within iteration-1 scope) =====

class TestRoundTrip:
    @pytest.mark.parametrize("xml", [
        b'<?xml version="1.0" encoding="UTF-8"?>\n<r/>',
        b'<?xml version="1.0" encoding="UTF-8"?>\n<r><x>hello</x></r>',
        b'<?xml version="1.0" encoding="UTF-8"?>\n<r a="1" b="2"><x>1</x><x>2</x></r>',
        b'<?xml version="1.0" encoding="UTF-8"?>\n<r><a><b><c d="e">x</c></b></a></r>',
        b'<?xml version="1.0" encoding="UTF-8"?>\n<r><x a="1">text</x></r>',
    ])
    def test_round_trip_stable(self, xml):
        # JSON stability under round-trip: parse -> serialize -> parse should fix-point.
        d1 = parse_xml_bytes(xml)
        re_xml = to_xml_string(d1).encode("utf-8")
        d2 = parse_xml_bytes(re_xml)
        assert d1 == d2

    def test_round_trip_entity_escape(self):
        # Special chars in text and attribute survive escape -> reparse.
        d1 = parse_xml_bytes(b'<r><x a="quote &quot;">a &amp; b &lt; c</x></r>')
        re_xml = to_xml_string(d1).encode("utf-8")
        d2 = parse_xml_bytes(re_xml)
        assert d1 == d2
        assert d1["r"]["x"]["@a"] == 'quote "'
        assert d1["r"]["x"]["_text"] == "a & b < c"


# ===== CDATA (iteration 2) =====

class TestCdata:
    def test_parse_cdata_text_only_element(self):
        result = parse_xml_bytes(
            b'<r><title><![CDATA[Hello <world>]]></title></r>'
        )
        assert result["r"] == {
            "_cdata": ["title"],
            "title": "Hello <world>",
        }

    def test_parse_cdata_with_attrs(self):
        result = parse_xml_bytes(
            b'<r><x a="1"><![CDATA[body]]></x></r>'
        )
        assert result["r"] == {
            "_cdata": ["x"],
            "x": {"@a": "1", "_text": "body"},
        }

    def test_parse_two_cdata_siblings_same_tag(self):
        result = parse_xml_bytes(
            b'<r><x><![CDATA[a]]></x><x><![CDATA[b]]></x></r>'
        )
        assert result["r"] == {
            "_cdata": ["x"],
            "x": ["a", "b"],
        }

    def test_parse_mixed_cdata_plain_within_element_rejected(self):
        with pytest.raises(CdataInconsistencyError):
            parse_xml_bytes(b'<r><x>plain<![CDATA[cdata]]></x></r>')

    def test_parse_inconsistent_cdata_across_siblings_rejected(self):
        with pytest.raises(CdataInconsistencyError):
            parse_xml_bytes(
                b'<r><x><![CDATA[a]]></x><x>plain</x></r>'
            )

    def test_serialize_cdata(self):
        data = {"r": {"_cdata": ["title"], "title": "Hello <world>"}}
        xml = to_xml_string(data)
        assert "<title><![CDATA[Hello <world>]]></title>" in xml

    def test_serialize_cdata_with_attrs(self):
        data = {"r": {"_cdata": ["x"], "x": {"@a": "1", "_text": "body"}}}
        xml = to_xml_string(data)
        assert '<x a="1"><![CDATA[body]]></x>' in xml

    def test_serialize_cdata_forbidden_sequence_rejected(self):
        data = {"r": {"_cdata": ["x"], "x": "contains ]]> sequence"}}
        with pytest.raises(MalformedJsonError):
            to_xml_string(data)

    def test_serialize_malformed_cdata_key_rejected(self):
        with pytest.raises(MalformedJsonError):
            to_xml_string({"r": {"_cdata": "not-a-list", "x": ""}})

    @pytest.mark.parametrize("xml", [
        b'<?xml version="1.0" encoding="UTF-8"?>\n<r><title><![CDATA[Hello <world>]]></title></r>',
        b'<?xml version="1.0" encoding="UTF-8"?>\n<r><body><![CDATA[multi\nline\ntext]]></body></r>',
        b'<?xml version="1.0" encoding="UTF-8"?>\n<r><x a="1"><![CDATA[body]]></x></r>',
        b'<?xml version="1.0" encoding="UTF-8"?>\n<r><x><![CDATA[a]]></x><x><![CDATA[b]]></x><y>plain</y></r>',
    ])
    def test_round_trip_cdata(self, xml):
        # Strict XML-equivalence round trip via the faithful tree comparator.
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from xml_compare import parse_faithful, diff_summary
        faithful_a = parse_faithful(xml)
        d = parse_xml_bytes(xml)
        re_xml = to_xml_string(d).encode("utf-8")
        faithful_b = parse_faithful(re_xml)
        diff = diff_summary(faithful_a, faithful_b)
        assert not diff, diff
