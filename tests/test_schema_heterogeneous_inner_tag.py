"""Unit tests for `gndson.schema.heterogeneous_inner_tag`."""

import pytest

from gndson.schema.arity import enforce_array_arity
from gndson.schema.base import Pipeline
from gndson.schema.heterogeneous_inner_tag import (
    DropHeterogeneousInnerTag,
    HETEROGENEOUS_PLURAL_CONTAINERS,
    drop_heterogeneous_inner_tag,
)
from gndson.schema.inner_tag import drop_uniform_inner_tag
from gndson.schema.physical_quantity import (
    augment_kind,
    collapse_physicalQuantity_wrappers,
)


# ===== Forward =====

class TestForward:
    def test_collapses_mixed_container_to_flat_list(self):
        data = {"function1ds": {
            "XYs1d":     [{"@index": "0"}, {"@index": "1"}],
            "regions1d": {"@a": "x"},
        }}
        out = drop_heterogeneous_inner_tag.forward(data)
        assert out == {"function1ds": [
            {"_kind": "XYs1d",     "@index": "0"},
            {"_kind": "XYs1d",     "@index": "1"},
            {"_kind": "regions1d", "@a":     "x"},
        ]}

    def test_preserves_kind_order_by_first_occurrence(self):
        # regions1d first, then XYs1d — order must be preserved in the
        # flat list.
        data = {"function1ds": {
            "regions1d": {"@a": "x"},
            "XYs1d":     [{"@index": "0"}, {"@index": "1"}],
        }}
        out = drop_heterogeneous_inner_tag.forward(data)
        kinds_in_order = [item["_kind"] for item in out["function1ds"]]
        assert kinds_in_order == ["regions1d", "XYs1d", "XYs1d"]

    def test_handles_axes_axis_and_grid(self):
        data = {"axes": {
            "axis": [{"@index": "1", "@label": "energy_in", "@unit": "eV"}],
            "grid": [{"@index": "0", "@label": "T", "@unit": "K"}],
        }}
        out = drop_heterogeneous_inner_tag.forward(data)
        kinds = sorted(item["_kind"] for item in out["axes"])
        assert kinds == ["axis", "grid"]

    def test_handles_aliases_alias_and_metaStable(self):
        data = {"aliases": {
            "alias":      [{"@id": "d", "@pid": "h2"}],
            "metaStable": [{"@id": "Al26_m1", "@pid": "Al26"}],
        }}
        out = drop_heterogeneous_inner_tag.forward(data)
        assert len(out["aliases"]) == 2
        assert {item["_kind"] for item in out["aliases"]} == {"alias", "metaStable"}

    def test_handles_empty_container(self):
        data = {"function1ds": {}}
        out = drop_heterogeneous_inner_tag.forward(data)
        assert out == {"function1ds": []}

    def test_skips_unknown_container(self):
        data = {"unrelated": {"foo": [{"@a": "1"}], "bar": [{"@b": "2"}]}}
        out = drop_heterogeneous_inner_tag.forward(data)
        assert out == data

    def test_skips_when_container_has_meta_key(self):
        data = {"function1ds": {
            "_comments": ["interp note"],
            "_order":    ["_comment", "XYs1d"],
            "XYs1d":     {"@index": "0"},
        }}
        out = drop_heterogeneous_inner_tag.forward(data)
        assert out == data

    def test_skips_when_container_has_attribute(self):
        data = {"function1ds": {
            "@some_attr": "x",
            "XYs1d":      {"@index": "0"},
        }}
        out = drop_heterogeneous_inner_tag.forward(data)
        assert out == data

    def test_skips_when_inner_is_bare_string(self):
        data = {"function1ds": {
            "XYs1d":     {"@index": "0"},
            "something": "just-a-string",
        }}
        out = drop_heterogeneous_inner_tag.forward(data)
        assert out == data

    def test_recurses_into_collapsed_list(self):
        # An XYs1d item contains its own <axes> heterogeneous container.
        # Canonical form: single XYs1d as scalar; single axis/grid as scalar.
        data = {"function1ds": {
            "XYs1d": {
                "@index": "0",
                "axes": {
                    "axis": {"@index": "1", "@unit": "eV"},
                    "grid": {"@index": "0", "@unit": "K"},
                },
                "values": "1 2 3",
            },
        }}
        out = drop_heterogeneous_inner_tag.forward(data)
        # Outer container collapsed:
        assert isinstance(out["function1ds"], list)
        # Inner axes ALSO collapsed (walker recurses into the new list):
        inner_axes = out["function1ds"][0]["axes"]
        assert isinstance(inner_axes, list)
        assert {item["_kind"] for item in inner_axes} == {"axis", "grid"}

    def test_does_not_mutate_input(self):
        data = {"function1ds": {"XYs1d": [{"@a": "1"}]}}
        before = {"function1ds": {"XYs1d": [{"@a": "1"}]}}
        _ = drop_heterogeneous_inner_tag.forward(data)
        assert data == before


# ===== Inverse =====

class TestInverse:
    def test_re_groups_flat_list_by_kind(self):
        data = {"function1ds": [
            {"_kind": "XYs1d",     "@index": "0"},
            {"_kind": "XYs1d",     "@index": "1"},
            {"_kind": "regions1d", "@a":     "x"},
        ]}
        out = drop_heterogeneous_inner_tag.inverse(data)
        assert out == {"function1ds": {
            "XYs1d":     [{"@index": "0"}, {"@index": "1"}],
            "regions1d": {"@a": "x"},
        }}

    def test_single_item_per_kind_becomes_scalar(self):
        # Canonical count-driven rule: one occurrence → scalar.
        data = {"axes": [
            {"_kind": "axis", "@index": "1"},
            {"_kind": "grid", "@index": "0"},
        ]}
        out = drop_heterogeneous_inner_tag.inverse(data)
        assert out == {"axes": {
            "axis": {"@index": "1"},
            "grid": {"@index": "0"},
        }}

    def test_empty_list_becomes_empty_dict(self):
        data = {"function1ds": []}
        out = drop_heterogeneous_inner_tag.inverse(data)
        assert out == {"function1ds": {}}

    def test_raises_on_item_missing_kind(self):
        data = {"function1ds": [{"@a": "1"}]}  # no _kind
        with pytest.raises(ValueError):
            drop_heterogeneous_inner_tag.inverse(data)

    def test_skips_unknown_container(self):
        data = {"unrelated": [{"_kind": "x", "@a": "1"}]}
        out = drop_heterogeneous_inner_tag.inverse(data)
        assert out == data

    def test_skips_when_value_is_dict(self):
        data = {"function1ds": {"XYs1d": {"@a": "1"}}}
        out = drop_heterogeneous_inner_tag.inverse(data)
        assert out == data


# ===== Forward then inverse is identity =====

class TestRoundTrip:
    @pytest.mark.parametrize("canonical", [
        # Multiple inner types, mixed scalar/list shapes (canonical form)
        {"function1ds": {
            "XYs1d":     [{"@index": "0"}, {"@index": "1"}],
            "regions1d": {"@a": "x"},
        }},
        # Single inner type only — still works
        {"function1ds": {"XYs1d": [{"@index": "0"}, {"@index": "1"}]}},
        # Empty container
        {"function1ds": {}},
        # axes with both axis and grid
        {"axes": {
            "axis": [{"@index": "1", "@unit": "eV"}, {"@index": "0", "@unit": "b"}],
            "grid": {"@index": "0", "@unit": "K"},
        }},
        # aliases with both inner types (single occurrence each → scalar in canonical)
        {"aliases": {
            "alias": {"@id": "d", "@pid": "h2"},
            "metaStable": {"@id": "Al26_m1", "@pid": "Al26"},
        }},
        # Container with meta — collapse skipped, round-trip identity holds
        {"function1ds": {
            "_comments": ["c"],
            "_order":    ["_comment", "XYs1d"],
            "XYs1d":     {"@index": "0"},
        }},
        # Nested heterogeneous (axes inside XYs1d inside function1ds).
        # Canonical form: single occurrences are scalars, not 1-element lists.
        {"function1ds": {
            "XYs1d": {
                "@index": "0",
                "axes": {
                    "axis": {"@index": "1"},
                    "grid": {"@index": "0"},
                },
                "values": "1 2 3",
            },
        }},
    ])
    def test_forward_then_inverse_is_identity(self, canonical):
        out = drop_heterogeneous_inner_tag.inverse(
            drop_heterogeneous_inner_tag.forward(canonical)
        )
        assert out == canonical


# ===== Full ergonomic_full pipeline =====

class TestErgonomicFullPipeline:
    """The full pipeline composing all four schema-layer steps:
    arity → inner_tag → augment_kind → collapse_physicalQuantity_wrappers
    → drop_heterogeneous_inner_tag. Round-trips canonical JSON exactly."""

    @pytest.mark.parametrize("canonical", [
        # PoPs slice with physicalQuantity wrappers and aliases container.
        {"reactionSuite": {
            "PoPs": {
                "aliases": {"alias": {"@id": "d", "@pid": "h2"}},
                "baryons": {"baryon": {
                    "@id": "n",
                    "mass":   {"double":   {"@value": "1.00866", "@unit": "amu"}},
                    "spin":   {"fraction": {"@value": "1/2", "@unit": "hbar"}},
                    "parity": {"integer":  {"@value": "1"}},
                }},
            },
        }},
        # Cross-section slice with function1ds and axes.
        # Canonical form: <axis> appears twice -> list of 2; <XYs1d> once
        # -> scalar.
        {"reactionSuite": {
            "reactions": {"reaction": {
                "@label": "n + H1",
                "crossSection": {
                    "regions1d": {
                        "@label": "eval",
                        "axes": {
                            "axis": [
                                {"@index": "1", "@label": "energy_in", "@unit": "eV"},
                                {"@index": "0", "@label": "crossSection", "@unit": "b"},
                            ],
                        },
                        "function1ds": {
                            "XYs1d": {"@index": "0", "values": "1 2 3 4"},
                        },
                    },
                },
            }},
        }},
    ])
    def test_ergonomic_full_round_trip(self, canonical):
        pipeline = Pipeline([
            enforce_array_arity,
            drop_uniform_inner_tag,
            augment_kind,
            collapse_physicalQuantity_wrappers,
            drop_heterogeneous_inner_tag,
        ])
        out = pipeline.inverse(pipeline.forward(canonical))
        assert out == canonical


# ===== Metadata sanity =====

class TestMetadata:
    def test_examples_round_trip(self):
        t = DropHeterogeneousInnerTag()
        assert t.forward(t.example_before) == t.example_after
        assert t.inverse(t.example_after) == t.example_before

    def test_declares_kind_witness(self):
        assert "_kind" in drop_heterogeneous_inner_tag.witnesses_added
        assert tuple(drop_heterogeneous_inner_tag.witnesses_consumed) == ()

    def test_dictionary_contains_expected_containers(self):
        for k in ("function1ds", "styles", "axes", "aliases"):
            assert k in HETEROGENEOUS_PLURAL_CONTAINERS

    def test_dictionary_disjoint_from_uniform_dictionary(self):
        # The uniform (step 1) and heterogeneous (step 4) dictionaries
        # must not overlap — every container is classified as exactly one.
        from gndson.schema.arity import UNIFORM_PLURAL_CONTAINERS
        assert not (
            HETEROGENEOUS_PLURAL_CONTAINERS & UNIFORM_PLURAL_CONTAINERS.keys()
        )

    def test_dictionary_disjoint_from_physicalQuantity_wrappers(self):
        # The physicalQuantity-wrapper set (step 3) and the heterogeneous-
        # container set must also be disjoint.
        from gndson.schema.physical_quantity import PHYSICAL_QUANTITY_WRAPPERS
        assert not (HETEROGENEOUS_PLURAL_CONTAINERS & PHYSICAL_QUANTITY_WRAPPERS)
