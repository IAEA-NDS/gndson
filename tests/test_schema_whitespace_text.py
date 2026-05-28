"""Unit tests for `gndson.schema.whitespace_text`."""

import pytest

from gndson.schema.whitespace_text import (
    SplitWhitespaceText,
    TOKENIZED_NUMERIC_TAGS,
    split_whitespace_text,
)


# ===== Forward =====

class TestForward:
    def test_splits_simple_text(self):
        data = {"values": "1.0 2.0 3.0"}
        out = split_whitespace_text.forward(data)
        assert out == {"values": ["1.0", "2.0", "3.0"]}

    def test_splits_on_runs_of_whitespace(self):
        data = {"values": "1.0\n  2.0\n  3.0"}
        out = split_whitespace_text.forward(data)
        # str.split() (no arg) splits on any whitespace run.
        assert out == {"values": ["1.0", "2.0", "3.0"]}

    def test_handles_leading_trailing_whitespace(self):
        data = {"values": "  1.0 2.0  "}
        out = split_whitespace_text.forward(data)
        assert out == {"values": ["1.0", "2.0"]}

    def test_empty_string_becomes_empty_list(self):
        data = {"values": ""}
        out = split_whitespace_text.forward(data)
        assert out == {"values": []}

    def test_whitespace_only_becomes_empty_list(self):
        data = {"values": "   \n  "}
        out = split_whitespace_text.forward(data)
        assert out == {"values": []}

    def test_skips_unknown_tag(self):
        data = {"unrelated": "1 2 3"}
        out = split_whitespace_text.forward(data)
        assert out == {"unrelated": "1 2 3"}

    def test_skips_when_value_is_not_string(self):
        # If `values` is already a list or a dict (e.g. wrapped form), skip.
        data = {"values": {"@a": "1"}}
        out = split_whitespace_text.forward(data)
        assert out == data

    def test_recurses_into_nested_structures(self):
        data = {
            "reactions": {
                "reaction": {
                    "crossSection": {
                        "XYs1d": {
                            "values": "1e-5 20.4 2e7 20.4",
                        },
                    },
                },
            },
        }
        out = split_whitespace_text.forward(data)
        assert out["reactions"]["reaction"]["crossSection"]["XYs1d"]["values"] == [
            "1e-5", "20.4", "2e7", "20.4",
        ]

    def test_does_not_mutate_input(self):
        data = {"values": "1 2 3"}
        before = {"values": "1 2 3"}
        _ = split_whitespace_text.forward(data)
        assert data == before


# ===== Inverse =====

class TestInverse:
    def test_joins_list_with_single_spaces(self):
        data = {"values": ["1.0", "2.0", "3.0"]}
        out = split_whitespace_text.inverse(data)
        assert out == {"values": "1.0 2.0 3.0"}

    def test_joins_empty_list_to_empty_string(self):
        data = {"values": []}
        out = split_whitespace_text.inverse(data)
        assert out == {"values": ""}

    def test_skips_when_value_is_not_list(self):
        data = {"values": "already a string"}
        out = split_whitespace_text.inverse(data)
        assert out == data

    def test_skips_unknown_tag(self):
        data = {"unrelated": ["1", "2", "3"]}
        out = split_whitespace_text.inverse(data)
        assert out == data

    def test_raises_on_non_string_list_items(self):
        # If a user / earlier transformation puts numbers in the list,
        # we don't silently coerce — raise instead.
        data = {"values": [1, 2, 3]}
        with pytest.raises(ValueError):
            split_whitespace_text.inverse(data)


# ===== Forward then inverse =====

class TestObjectForm:
    """`<values>` can have attributes (start, length for zero-compression
    per GNDS §5.2.1); then it's in object form with `_text`."""

    def test_forward_splits_text_under_attrs(self):
        data = {"values": {"@start": "3", "@length": "5", "_text": "1 2 3"}}
        out = split_whitespace_text.forward(data)
        assert out == {"values": {"@start": "3", "@length": "5",
                                  "_text": ["1", "2", "3"]}}

    def test_inverse_joins_text_under_attrs(self):
        data = {"values": {"@start": "3", "_text": ["1", "2", "3"]}}
        out = split_whitespace_text.inverse(data)
        assert out == {"values": {"@start": "3", "_text": "1 2 3"}}

    def test_round_trip_object_form(self):
        data = {"values": {"@start": "3", "@length": "5", "_text": "1.0 2.0"}}
        out = split_whitespace_text.inverse(split_whitespace_text.forward(data))
        assert out == data


class TestMultiOccurrence:
    """Multiple `<values>` siblings under one parent give a list-valued
    `values` key. Forward produces nested lists so the inverse can
    distinguish multi-occurrence from single-occurrence post-forward."""

    def test_forward_all_bare_strings(self):
        # Canonical: two <values> siblings, both bare-string form.
        data = {"parent": {"values": ["a b", "c d"]}}
        out = split_whitespace_text.forward(data)
        assert out == {"parent": {"values": [["a", "b"], ["c", "d"]]}}

    def test_forward_mixed_bare_and_object(self):
        # The exact shape that failed in the corpus pre-fix: list with
        # both a dict item (object form with attrs) and a string item.
        data = {"parent": {"values": [
            {"@start": "0", "_text": "a b"},
            "c d e",
        ]}}
        out = split_whitespace_text.forward(data)
        assert out == {"parent": {"values": [
            {"@start": "0", "_text": ["a", "b"]},
            ["c", "d", "e"],
        ]}}

    def test_inverse_re_joins_nested(self):
        data = {"parent": {"values": [["a", "b"], ["c", "d"]]}}
        out = split_whitespace_text.inverse(data)
        assert out == {"parent": {"values": ["a b", "c d"]}}

    @pytest.mark.parametrize("data", [
        # All bare-string multi (typical multi)
        {"parent": {"values": ["1 2 3", "4 5 6"]}},
        # Single-token bodies (would be ambiguous without nesting)
        {"parent": {"values": ["5", "10"]}},
        # All object form multi
        {"parent": {"values": [
            {"@a": "1", "_text": "x y"},
            {"@b": "2", "_text": "z w"},
        ]}},
        # Mixed multi (the corpus case)
        {"parent": {"values": [
            {"@start": "0", "_text": "a b"},
            "c d e",
        ]}},
    ])
    def test_round_trip_multi_occurrence(self, data):
        out = split_whitespace_text.inverse(split_whitespace_text.forward(data))
        assert out == data


class TestRoundTripSingleOccurrence:
    @pytest.mark.parametrize("data", [
        # Clean single-space input: bijective at the byte level.
        {"values": "1.0 2.0 3.0"},
        {"values": ""},
        # Single-occurrence inside a realistic deep nesting.
        {"reactionSuite": {"reactions": {"reaction": {
            "crossSection": {"XYs1d": {"values": "1e-5 20.4 2e7 20.4"}}
        }}}},
    ])
    def test_forward_then_inverse_byte_identity(self, data):
        """When the input is in single-space canonical form, the round-trip
        is bijective at the byte level."""
        out = split_whitespace_text.inverse(split_whitespace_text.forward(data))
        assert out == data

    @pytest.mark.parametrize("data", [
        # Multi-line / indented input: byte-different, but spec-equivalent.
        {"values": "1.0\n  2.0\n  3.0"},
        {"values": "  1.0 2.0  "},
        {"values": "1.0  2.0   3.0"},  # runs of multiple spaces
    ])
    def test_forward_then_inverse_normalises_whitespace(self, data):
        """For non-canonical whitespace input, the round-trip is only
        bijective up to whitespace normalisation."""
        out = split_whitespace_text.inverse(split_whitespace_text.forward(data))
        # The values' token-level content matches:
        assert out["values"].split() == data["values"].split()
        # ... but the strings themselves differ (whitespace collapsed).
        assert out != data


# ===== Metadata sanity =====

class TestMetadata:
    def test_examples_round_trip(self):
        t = SplitWhitespaceText()
        assert t.forward(t.example_before) == t.example_after
        assert t.inverse(t.example_after) == t.example_before

    def test_no_witness_keys_declared(self):
        # The dictionary is the witness; no JSON-level witness needed.
        assert tuple(split_whitespace_text.witnesses_added) == ()
        assert tuple(split_whitespace_text.witnesses_consumed) == ()

    def test_dictionary_includes_values(self):
        assert "values" in TOKENIZED_NUMERIC_TAGS
