"""Unit tests for `gndson.schema.physical_quantity`."""

import pytest

from gndson.schema.arity import enforce_array_arity
from gndson.schema.base import Pipeline
from gndson.schema.inner_tag import drop_uniform_inner_tag
from gndson.schema.physical_quantity import (
    AugmentKind,
    CollapsePhysicalQuantityWrappers,
    PHYSICAL_QUANTITY_WRAPPERS,
    augment_kind,
    collapse_physicalQuantity_wrappers,
)


# ===== augment_kind forward =====

class TestAugmentKindForward:
    def test_annotates_basic_wrapper(self):
        data = {"mass": {"double": {"@value": "1.0", "@unit": "amu"}}}
        out = augment_kind.forward(data)
        assert out == {"mass": {
            "_kind": "double",
            "double": {"@value": "1.0", "@unit": "amu"},
        }}

    def test_annotates_each_wrapper_type(self):
        data = {
            "nucleus": {
                "mass":     {"double":   {"@value": "1.0"}},
                "spin":     {"fraction": {"@value": "1/2"}},
                "parity":   {"integer":  {"@value": "1"}},
                "charge":   {"integer":  {"@value": "1"}},
                "halflife": {"string":   {"@value": "stable"}},
                "energy":   {"double":   {"@value": "0"}},
            }
        }
        out = augment_kind.forward(data)
        for k, expected_kind in [
            ("mass", "double"), ("spin", "fraction"), ("parity", "integer"),
            ("charge", "integer"), ("halflife", "string"), ("energy", "double"),
        ]:
            assert out["nucleus"][k]["_kind"] == expected_kind

    def test_skips_multi_occurrence_inner(self):
        # Style-labelled alternates: spin with two fraction children.
        data = {"spin": {"fraction": [{"@value": "1/2"}, {"@value": "3/2"}]}}
        out = augment_kind.forward(data)
        assert "_kind" not in out["spin"]

    def test_skips_heterogeneous_inner(self):
        # charge with both integer and fraction children.
        data = {"charge": {
            "integer":  {"@value": "1"},
            "fraction": {"@value": "1/2"},
        }}
        out = augment_kind.forward(data)
        assert "_kind" not in out["charge"]

    def test_skips_wrapper_with_attribute(self):
        # Spec example p.167 shows <spin recommended="eval">; even though
        # the prose says wrappers have no attributes, we tolerate the
        # case by skipping it rather than crashing.
        data = {"spin": {
            "@recommended": "eval",
            "fraction": {"@value": "1/2"},
        }}
        out = augment_kind.forward(data)
        assert "_kind" not in out["spin"]

    def test_skips_wrapper_with_meta_key(self):
        data = {"mass": {
            "_comments": ["uncertain"],
            "_order": ["_comment", "double"],
            "double": {"@value": "1.0"},
        }}
        out = augment_kind.forward(data)
        assert "_kind" not in out["mass"]

    def test_skips_empty_wrapper(self):
        # <probability></probability> -> bare string "" canonical form.
        data = {"probability": ""}
        out = augment_kind.forward(data)
        assert out == data

    def test_skips_non_wrapper_tag(self):
        data = {"reactions": {"reaction": {"@a": "1"}}}
        out = augment_kind.forward(data)
        assert "_kind" not in out["reactions"]

    def test_does_not_mutate_input(self):
        data = {"mass": {"double": {"@value": "1.0"}}}
        before = {"mass": {"double": {"@value": "1.0"}}}
        _ = augment_kind.forward(data)
        assert data == before

    def test_idempotent_under_repeated_application(self):
        data = {"mass": {"double": {"@value": "1.0"}}}
        once = augment_kind.forward(data)
        twice = augment_kind.forward(once)
        assert twice == once

    def test_handles_Q_with_functional_inner(self):
        # Q's inner is one of constant1d / XYs1d / regions1d / ... — not
        # the basic double/integer/fraction/string. augment_kind still
        # treats it as a wrapper because the tag is in the dictionary
        # and the structural rules match.
        data = {"Q": {"constant1d": {
            "@label": "eval", "@value": "0",
            "axes": {"axis": []},
        }}}
        out = augment_kind.forward(data)
        assert out["Q"]["_kind"] == "constant1d"


# ===== augment_kind inverse =====

class TestAugmentKindInverse:
    def test_strips_kind(self):
        data = {"mass": {"_kind": "double", "double": {"@value": "1.0"}}}
        out = augment_kind.inverse(data)
        assert out == {"mass": {"double": {"@value": "1.0"}}}

    def test_no_op_when_kind_absent(self):
        data = {"reactions": {"reaction": {"@a": "1"}}}
        out = augment_kind.inverse(data)
        assert out == data

    def test_strips_recursively(self):
        data = {"reactionSuite": {
            "mass": {"_kind": "double", "double": {"@value": "1.0"}},
            "spin": {"_kind": "fraction", "fraction": {"@value": "1/2"}},
        }}
        out = augment_kind.inverse(data)
        assert "_kind" not in out["reactionSuite"]["mass"]
        assert "_kind" not in out["reactionSuite"]["spin"]


# ===== augment_kind round-trip =====

class TestAugmentKindRoundTrip:
    @pytest.mark.parametrize("data", [
        {"mass": {"double": {"@value": "1.0"}}},
        {"spin": {"fraction": [{"@value": "1/2"}, {"@value": "3/2"}]}},  # not augmented
        {"charge": {"integer": {"@value": "1"}, "fraction": {"@value": "1/2"}}},  # not augmented
        {"probability": ""},  # empty
        {"reactionSuite": {
            "PoPs": {"baryons": {"baryon": {
                "@id": "n",
                "mass": {"double": {"@value": "1.0"}},
                "spin": {"fraction": {"@value": "1/2"}},
            }}},
        }},
    ])
    def test_forward_then_inverse_is_identity(self, data):
        out = augment_kind.inverse(augment_kind.forward(data))
        assert out == data


# ===== collapse forward =====

class TestCollapseForward:
    def test_hoists_inner_attrs(self):
        data = {"mass": {
            "_kind": "double",
            "double": {"@value": "1.0", "@unit": "amu"},
        }}
        out = collapse_physicalQuantity_wrappers.forward(data)
        assert out == {"mass": {
            "_kind": "double",
            "@value": "1.0",
            "@unit": "amu",
        }}

    def test_hoists_inner_children(self):
        data = {"mass": {
            "_kind": "double",
            "double": {
                "@value": "1.0",
                "uncertainty": {"@a": "1"},
            },
        }}
        out = collapse_physicalQuantity_wrappers.forward(data)
        assert out == {"mass": {
            "_kind": "double",
            "@value": "1.0",
            "uncertainty": {"@a": "1"},
        }}

    def test_no_op_when_kind_absent(self):
        data = {"mass": {"double": {"@value": "1.0"}}}
        out = collapse_physicalQuantity_wrappers.forward(data)
        assert out == data

    def test_no_op_when_already_hoisted(self):
        # _kind present, no matching inner child — already in collapsed form.
        data = {"mass": {"_kind": "double", "@value": "1.0"}}
        out = collapse_physicalQuantity_wrappers.forward(data)
        assert out == data

    def test_raises_on_hoist_conflict(self):
        # Pathological: wrapper somehow has a key that the inner also has.
        data = {"mass": {
            "_kind": "double",
            "@unit": "kg",  # wrapper-level
            "double": {"@unit": "amu"},  # inner-level — would overwrite
        }}
        with pytest.raises(ValueError):
            collapse_physicalQuantity_wrappers.forward(data)

    def test_does_not_mutate_input(self):
        data = {"mass": {"_kind": "double", "double": {"@value": "1.0"}}}
        before = {"mass": {"_kind": "double", "double": {"@value": "1.0"}}}
        _ = collapse_physicalQuantity_wrappers.forward(data)
        assert data == before


# ===== collapse inverse =====

class TestCollapseInverse:
    def test_rebuilds_inner_from_kind(self):
        data = {"mass": {
            "_kind": "double",
            "@value": "1.0",
            "@unit": "amu",
        }}
        out = collapse_physicalQuantity_wrappers.inverse(data)
        assert out == {"mass": {
            "_kind": "double",
            "double": {"@value": "1.0", "@unit": "amu"},
        }}

    def test_no_op_when_kind_absent(self):
        data = {"mass": {"double": {"@value": "1.0"}}}
        out = collapse_physicalQuantity_wrappers.inverse(data)
        assert out == data

    def test_no_op_when_inner_already_present(self):
        # _kind plus existing inner of that name — already in
        # pre-collapse (post-augment) form.
        data = {"mass": {
            "_kind": "double",
            "double": {"@value": "1.0"},
        }}
        out = collapse_physicalQuantity_wrappers.inverse(data)
        assert out == data


# ===== collapse round-trip =====

class TestCollapseRoundTrip:
    @pytest.mark.parametrize("data", [
        {"mass": {"_kind": "double", "double": {"@value": "1.0"}}},
        {"spin": {"_kind": "fraction", "fraction": {"@value": "1/2", "@unit": "hbar"}}},
        # No _kind anywhere - identity pass-through
        {"reactions": {"reaction": [{"@a": "1"}]}},
    ])
    def test_forward_then_inverse_is_identity(self, data):
        out = collapse_physicalQuantity_wrappers.inverse(
            collapse_physicalQuantity_wrappers.forward(data)
        )
        assert out == data


# ===== Pipeline: augment + collapse =====

class TestPipelineAugmentCollapse:
    @pytest.mark.parametrize("canonical", [
        {"mass": {"double": {"@value": "1.0", "@unit": "amu"}}},
        {"spin": {"fraction": {"@value": "1/2", "@unit": "hbar"}}},
        # Multi-occurrence — not collapsed; passes through identically.
        {"spin": {"fraction": [{"@value": "1/2"}, {"@value": "3/2"}]}},
        # Heterogeneous — not collapsed.
        {"charge": {"integer": {"@value": "1"}, "fraction": {"@value": "1/2"}}},
        # Wrapper with attribute — not collapsed.
        {"spin": {"@recommended": "eval", "fraction": {"@value": "1/2"}}},
        # Nested wrappers inside a non-wrapper container.
        {"baryon": {
            "@id": "n",
            "mass":   {"double":   {"@value": "1.00866"}},
            "spin":   {"fraction": {"@value": "1/2"}},
            "parity": {"integer":  {"@value": "1"}},
        }},
    ])
    def test_round_trip_through_pipeline(self, canonical):
        pipeline = Pipeline([augment_kind, collapse_physicalQuantity_wrappers])
        out = pipeline.inverse(pipeline.forward(canonical))
        assert out == canonical

    def test_collapse_visibly_simplifies_eligible_wrapper(self):
        pipeline = Pipeline([augment_kind, collapse_physicalQuantity_wrappers])
        data = {"mass": {"double": {"@value": "1.0", "@unit": "amu"}}}
        out = pipeline.forward(data)
        assert out == {"mass": {
            "_kind": "double",
            "@value": "1.0",
            "@unit": "amu",
        }}


# ===== Full ERGONOMIC pipeline =====

class TestErgonomicPipeline:
    """Pipeline [arity, inner_tag, augment_kind, collapse] round-trips
    canonical JSON exactly. This is the recommended default named pipeline."""

    @pytest.mark.parametrize("canonical", [
        # Realistic PoPs slice
        {"reactionSuite": {
            "PoPs": {
                "baryons": {"baryon": {
                    "@id": "n",
                    "mass":   {"double":   {"@value": "1.0", "@unit": "amu"}},
                    "spin":   {"fraction": {"@value": "1/2", "@unit": "hbar"}},
                    "parity": {"integer":  {"@value": "1"}},
                }},
            },
        }},
        # Multiple baryons (list form on the canonical side)
        {"PoPs": {"baryons": {"baryon": [
            {"@id": "n", "mass": {"double": {"@value": "1.00866"}}},
            {"@id": "p", "mass": {"double": {"@value": "1.00728"}}},
        ]}}},
        # Non-augmented wrapper (heterogeneous charge)
        {"nucleus": {
            "charge": {"integer": {"@value": "1"}, "fraction": {"@value": "1/2"}},
        }},
    ])
    def test_ergonomic_round_trip(self, canonical):
        pipeline = Pipeline([
            enforce_array_arity,
            drop_uniform_inner_tag,
            augment_kind,
            collapse_physicalQuantity_wrappers,
        ])
        out = pipeline.inverse(pipeline.forward(canonical))
        assert out == canonical


# ===== Metadata sanity =====

class TestMetadata:
    def test_augment_kind_examples_round_trip(self):
        t = AugmentKind()
        assert t.forward(t.example_before) == t.example_after
        assert t.inverse(t.example_after) == t.example_before

    def test_collapse_examples_round_trip(self):
        t = CollapsePhysicalQuantityWrappers()
        assert t.forward(t.example_before) == t.example_after
        assert t.inverse(t.example_after) == t.example_before

    def test_augment_kind_declares_kind_witness(self):
        assert "_kind" in augment_kind.witnesses_added
        assert tuple(augment_kind.witnesses_consumed) == ()

    def test_collapse_does_not_consume_kind(self):
        # _kind is READ by collapse but persists in the end-state JSON
        # as the witness for the inverse — so it is NOT consumed in the
        # framework's witness-flow sense.
        assert tuple(collapse_physicalQuantity_wrappers.witnesses_added) == ()
        assert tuple(collapse_physicalQuantity_wrappers.witnesses_consumed) == ()

    def test_wrapper_dictionary_matches_spec(self):
        # Exactly the 8 tags declared as physicalQuantityNode in GNDS 2.1.
        assert PHYSICAL_QUANTITY_WRAPPERS == frozenset({
            "mass", "charge", "spin", "parity", "halflife", "energy",
            "Q", "probability",
        })
