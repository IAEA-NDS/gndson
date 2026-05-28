"""Unit tests for `gndson.schema.data_columns.expand_data_columns`."""

import pytest

from gndson.schema.data_columns import (
    ExpandDataColumns,
    expand_data_columns,
)


# ===== Forward =====

class TestForward:
    def test_expands_basic_data_table(self):
        data = {"data": {
            "_text": ["\n  ", "\n  1 2 3\n  4 5 6\n"],
            "_comments": ["a | b | c"],
            "_order": ["_text", "_comment", "_text"],
        }}
        out = expand_data_columns.forward(data)
        assert out["data"]["_columns"] == ["a", "b", "c"]
        assert out["data"]["_rows"] == [["1", "2", "3"], ["4", "5", "6"]]
        # Originals preserved unchanged.
        assert out["data"]["_text"] == ["\n  ", "\n  1 2 3\n  4 5 6\n"]
        assert out["data"]["_comments"] == ["a | b | c"]
        assert out["data"]["_order"] == ["_text", "_comment", "_text"]

    def test_handles_realistic_resonance_header(self):
        data = {"data": {
            "_text": [
                "\n     ",
                "\n  -10740 0 0.5 102.6217 101.7507 0.871\n",
            ],
            "_comments": [
                " energy | L | J | totalWidth | neutronWidth | captureWidth "
            ],
            "_order": ["_text", "_comment", "_text"],
        }}
        out = expand_data_columns.forward(data)
        assert out["data"]["_columns"] == [
            "energy", "L", "J", "totalWidth", "neutronWidth", "captureWidth"
        ]
        assert out["data"]["_rows"] == [
            ["-10740", "0", "0.5", "102.6217", "101.7507", "0.871"],
        ]

    def test_handles_multi_comment_takes_first_as_header(self):
        # When <data> has multiple comments (FUDGE multi-line headers),
        # we use the first as the primary header; subsequent comments
        # stay in _comments unchanged.
        data = {"data": {
            "_text": ["\n", "\n  1 2 3\n  4 5 6\n"],
            "_comments": ["a | b | c", "   |  width | width"],
            "_order": ["_text", "_comment", "_comment", "_text"],
        }}
        out = expand_data_columns.forward(data)
        assert out["data"]["_columns"] == ["a", "b", "c"]
        assert out["data"]["_rows"] == [["1", "2", "3"], ["4", "5", "6"]]
        # Both comments preserved verbatim.
        assert out["data"]["_comments"] == ["a | b | c", "   |  width | width"]

    def test_skips_data_without_comment(self):
        data = {"data": {"_text": "  1 2 3  "}}
        out = expand_data_columns.forward(data)
        assert "_columns" not in out["data"]
        assert "_rows" not in out["data"]

    def test_skips_comment_without_pipe(self):
        data = {"data": {
            "_text": ["", "1 2 3"],
            "_comments": ["just a note"],
            "_order": ["_text", "_comment", "_text"],
        }}
        out = expand_data_columns.forward(data)
        assert "_columns" not in out["data"]

    def test_skips_single_column_header(self):
        data = {"data": {
            "_text": ["", "1 2 3"],
            "_comments": ["just_one_column"],
            "_order": ["_text", "_comment", "_text"],
        }}
        out = expand_data_columns.forward(data)
        # split on '|' yields one piece; require >=2 columns.
        assert "_columns" not in out["data"]

    def test_skips_when_columns_are_empty(self):
        data = {"data": {
            "_text": ["", "1 2 3"],
            "_comments": [" | | "],
            "_order": ["_text", "_comment", "_text"],
        }}
        out = expand_data_columns.forward(data)
        # Empty column names → skip.
        assert "_columns" not in out["data"]

    def test_skips_when_body_does_not_divide_evenly(self):
        # 5 tokens, 3 columns → 5 % 3 != 0 → skip.
        data = {"data": {
            "_text": ["", "1 2 3 4 5"],
            "_comments": ["a | b | c"],
            "_order": ["_text", "_comment", "_text"],
        }}
        out = expand_data_columns.forward(data)
        assert "_columns" not in out["data"]

    def test_skips_when_body_is_empty(self):
        data = {"data": {
            "_text": "",
            "_comments": ["a | b | c"],
        }}
        out = expand_data_columns.forward(data)
        assert "_columns" not in out["data"]

    def test_skips_non_data_tag(self):
        # Comment with pipes on a different tag — no augmentation.
        data = {"otherTag": {
            "_text": "1 2 3",
            "_comments": ["a | b | c"],
        }}
        out = expand_data_columns.forward(data)
        assert "_columns" not in out["otherTag"]

    def test_handles_string_form_text(self):
        # _text can be a string (when only one text segment) instead of a list.
        data = {"data": {
            "_text": "  1 2\n  3 4\n",
            "_comments": ["a | b"],
        }}
        out = expand_data_columns.forward(data)
        assert out["data"]["_columns"] == ["a", "b"]
        assert out["data"]["_rows"] == [["1", "2"], ["3", "4"]]

    def test_idempotent(self):
        data = {"data": {
            "_text": "1 2 3 4",
            "_comments": ["a | b"],
        }}
        once = expand_data_columns.forward(data)
        twice = expand_data_columns.forward(once)
        assert twice == once

    def test_recurses_into_nested_data(self):
        # A <data> element inside a deeper structure.
        data = {"reactionSuite": {"resonances": {"resolved": {"BreitWigner": {
            "resonanceParameters": {"table": {"data": {
                "_text": ["", "1 2 3 4"],
                "_comments": ["x | y"],
                "_order": ["_text", "_comment", "_text"],
            }}}
        }}}}}
        out = expand_data_columns.forward(data)
        leaf = out["reactionSuite"]["resonances"]["resolved"]["BreitWigner"][
            "resonanceParameters"]["table"]["data"]
        assert leaf["_columns"] == ["x", "y"]
        assert leaf["_rows"] == [["1", "2"], ["3", "4"]]

    def test_does_not_mutate_input(self):
        data = {"data": {"_text": "1 2", "_comments": ["a | b"]}}
        before = {"data": {"_text": "1 2", "_comments": ["a | b"]}}
        _ = expand_data_columns.forward(data)
        assert data == before


# ===== Inverse =====

class TestInverse:
    def test_strips_columns_and_rows(self):
        data = {"data": {
            "_text": "1 2 3 4",
            "_comments": ["a | b"],
            "_columns": ["a", "b"],
            "_rows": [["1", "2"], ["3", "4"]],
        }}
        out = expand_data_columns.inverse(data)
        assert "_columns" not in out["data"]
        assert "_rows" not in out["data"]
        assert out["data"]["_text"] == "1 2 3 4"
        assert out["data"]["_comments"] == ["a | b"]

    def test_no_op_when_keys_absent(self):
        data = {"data": {"_text": "1 2", "_comments": ["a | b"]}}
        out = expand_data_columns.inverse(data)
        assert out == data

    def test_strips_recursively(self):
        data = {"outer": {"data": {
            "_text": "1 2", "_columns": ["a", "b"], "_rows": [["1", "2"]]
        }}}
        out = expand_data_columns.inverse(data)
        assert "_columns" not in out["outer"]["data"]
        assert "_rows" not in out["outer"]["data"]


# ===== Round-trip =====

class TestRoundTrip:
    @pytest.mark.parametrize("data", [
        # Single comment header
        {"data": {
            "_text": ["\n", "\n  1 2 3\n  4 5 6\n"],
            "_comments": ["a | b | c"],
            "_order": ["_text", "_comment", "_text"],
        }},
        # Multi comment (only first is the parsed header)
        {"data": {
            "_text": ["\n", "\n  1 2\n  3 4\n"],
            "_comments": ["a | b", "x | y"],
            "_order": ["_text", "_comment", "_comment", "_text"],
        }},
        # Non-matching data (no comment) — pass-through identity
        {"data": {"_text": "raw text body"}},
        # Non-matching data (comment without pipes) — pass-through
        {"data": {"_text": "1 2 3", "_comments": ["a note"]}},
        # No data tag at all
        {"otherTag": {"_text": "1 2 3", "_comments": ["a | b"]}},
    ])
    def test_forward_then_inverse_is_identity(self, data):
        out = expand_data_columns.inverse(expand_data_columns.forward(data))
        assert out == data


# ===== Metadata =====

class TestMetadata:
    def test_examples_round_trip(self):
        t = ExpandDataColumns()
        assert t.forward(t.example_before) == t.example_after
        assert t.inverse(t.example_after) == t.example_before

    def test_declares_witnesses(self):
        assert set(expand_data_columns.witnesses_added) == {"_columns", "_rows"}
        assert tuple(expand_data_columns.witnesses_consumed) == ()
