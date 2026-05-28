"""Unit tests for `gndson.schema.inner_tag.drop_uniform_inner_tag`."""

import pytest

from gndson.schema.arity import enforce_array_arity
from gndson.schema.base import Pipeline
from gndson.schema.inner_tag import (
    DropUniformInnerTag,
    drop_uniform_inner_tag,
)


# ===== Forward direction =====

class TestForward:
    def test_collapses_list_value(self):
        data = {"reactions": {"reaction": [{"@a": "1"}, {"@a": "2"}]}}
        out = drop_uniform_inner_tag.forward(data)
        assert out == {"reactions": [{"@a": "1"}, {"@a": "2"}]}

    def test_collapses_scalar_value(self):
        # When step 2 is used standalone (without prior arity normalisation),
        # a single-occurrence scalar gets wrapped and collapsed in one step.
        data = {"reactions": {"reaction": {"@a": "x"}}}
        out = drop_uniform_inner_tag.forward(data)
        assert out == {"reactions": [{"@a": "x"}]}

    def test_collapses_empty_container(self):
        # `{Xs: {}}` (no inner present) becomes `{Xs: []}`.
        data = {"reactions": {}}
        out = drop_uniform_inner_tag.forward(data)
        assert out == {"reactions": []}

    def test_collapses_empty_list(self):
        # `{Xs: {X: []}}` becomes `{Xs: []}`.
        data = {"reactions": {"reaction": []}}
        out = drop_uniform_inner_tag.forward(data)
        assert out == {"reactions": []}

    def test_skips_unknown_container(self):
        data = {"unrelated": {"child": [{"@a": "1"}]}}
        out = drop_uniform_inner_tag.forward(data)
        assert out == data

    def test_skips_when_comments_present(self):
        # Step 2 must NOT silently drop comments. When meta keys are
        # present, the container is left intact.
        data = {
            "reactions": {
                "_order": ["_comment", "reaction"],
                "_comments": ["elastic"],
                "reaction": [{"@a": "1"}],
            }
        }
        out = drop_uniform_inner_tag.forward(data)
        assert out == data

    def test_skips_when_attributes_present(self):
        # Hypothetical: container has attributes. Don't collapse.
        data = {"reactions": {"@some_attr": "x", "reaction": [{"@a": "1"}]}}
        out = drop_uniform_inner_tag.forward(data)
        assert out == data

    def test_skips_when_extra_sibling_tag_present(self):
        data = {
            "reactions": {
                "reaction": [{"@a": "1"}],
                "unexpected": [{"@b": "2"}],
            }
        }
        out = drop_uniform_inner_tag.forward(data)
        assert out == data

    def test_recurses_into_collapsed_list(self):
        # After collapsing the outer, walk into the list items so a nested
        # plural container also gets collapsed.
        data = {
            "reactions": {
                "reaction": [
                    {"products": {"product": [{"@pid": "n"}]}},
                    {"products": {"product": [{"@pid": "H1"}]}},
                ]
            }
        }
        out = drop_uniform_inner_tag.forward(data)
        assert out["reactions"][0]["products"] == [{"@pid": "n"}]
        assert out["reactions"][1]["products"] == [{"@pid": "H1"}]

    def test_does_not_mutate_input(self):
        data = {"reactions": {"reaction": [{"@a": "1"}]}}
        before = {"reactions": {"reaction": [{"@a": "1"}]}}
        _ = drop_uniform_inner_tag.forward(data)
        assert data == before


# ===== Inverse direction =====

class TestInverse:
    def test_wraps_list_under_inner_tag(self):
        data = {"reactions": [{"@a": "1"}, {"@a": "2"}]}
        out = drop_uniform_inner_tag.inverse(data)
        assert out == {"reactions": {"reaction": [{"@a": "1"}, {"@a": "2"}]}}

    def test_wraps_empty_list(self):
        data = {"reactions": []}
        out = drop_uniform_inner_tag.inverse(data)
        assert out == {"reactions": {"reaction": []}}

    def test_skips_when_already_dict(self):
        data = {"reactions": {"reaction": [{"@a": "1"}]}}
        out = drop_uniform_inner_tag.inverse(data)
        assert out == data

    def test_skips_unknown_container(self):
        data = {"unrelated": [{"@a": "1"}]}
        out = drop_uniform_inner_tag.inverse(data)
        assert out == data


# ===== Forward then inverse is identity (post-arity input shapes) =====

class TestRoundTripOnPostArityInput:
    """Round-trip on inputs that look like the output of `enforce_array_arity`
    (always-list discipline). For these inputs the forward + inverse of
    `drop_uniform_inner_tag` alone is identity."""

    @pytest.mark.parametrize("data", [
        {"reactions": {"reaction": [{"@a": "1"}]}},
        {"reactions": {"reaction": [{"@a": "1"}, {"@a": "2"}, {"@a": "3"}]}},
        {"reactions": {"reaction": []}},
        {"reactionSuite": {
            "reactions": {"reaction": [{"@a": "x"}]},
            "PoPs": {"baryons": {"baryon": [{"@id": "n"}, {"@id": "p"}]}},
        }},
        # Container with comments — collapse is skipped, round-trip identity holds.
        {"reactions": {
            "_order": ["_comment", "reaction"],
            "_comments": ["c"],
            "reaction": [{"@a": "1"}],
        }},
    ])
    def test_forward_then_inverse_is_identity(self, data):
        out = drop_uniform_inner_tag.inverse(drop_uniform_inner_tag.forward(data))
        assert out == data


# ===== Pipeline [arity, inner_tag] round-trips on canonical input =====

class TestPipelineWithArity:
    """The intended pipeline composes `enforce_array_arity` then
    `drop_uniform_inner_tag`. This composition round-trips canonical
    JSON exactly."""

    @pytest.mark.parametrize("canonical", [
        # Single occurrence (scalar in canonical form).
        {"reactions": {"reaction": {"@label": "x"}}},
        # Multiple occurrences (list in canonical form).
        {"reactions": {"reaction": [{"@a": "1"}, {"@a": "2"}]}},
        # Zero occurrences (key absent in canonical form — no `reactions` key
        # at all here means the parent doesn't have it; we use empty container
        # to represent the post-step-1 zero-occurrence form being preserved).
        {"reactionSuite": {"reactions": {"reaction": {"@label": "x"}}}},
        # Mixed plural containers.
        {"reactionSuite": {
            "reactions": {"reaction": {"@label": "x"}},
            "PoPs": {"baryons": {"baryon": [{"@id": "n"}, {"@id": "p"}]}},
        }},
        # Plural container WITH comments — pipeline preserves it as-is.
        {"reactionSuite": {"reactions": {
            "_order": ["_comment", "reaction"],
            "_comments": ["elastic"],
            "reaction": {"@a": "1"},
        }}},
    ])
    def test_round_trip_through_pipeline(self, canonical):
        pipeline = Pipeline([enforce_array_arity, drop_uniform_inner_tag])
        out = pipeline.inverse(pipeline.forward(canonical))
        assert out == canonical


# ===== Metadata sanity =====

class TestMetadata:
    def test_examples_round_trip(self):
        t = DropUniformInnerTag()
        assert t.forward(t.example_before) == t.example_after
        assert t.inverse(t.example_after) == t.example_before

    def test_no_witness_keys_declared(self):
        assert tuple(drop_uniform_inner_tag.witnesses_added) == ()
        assert tuple(drop_uniform_inner_tag.witnesses_consumed) == ()
