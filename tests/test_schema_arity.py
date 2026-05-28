"""Unit tests for `gndson.schema.arity.enforce_array_arity`."""

import pytest

from gndson.schema.arity import (
    EnforceArrayArity,
    UNIFORM_PLURAL_CONTAINERS,
    enforce_array_arity,
)


# ===== Forward direction =====

class TestForward:
    def test_wraps_scalar_in_list(self):
        data = {"reactions": {"reaction": {"@label": "n + H1"}}}
        out = enforce_array_arity.forward(data)
        assert out == {"reactions": {"reaction": [{"@label": "n + H1"}]}}

    def test_leaves_existing_list_alone(self):
        data = {"reactions": {"reaction": [{"@label": "a"}, {"@label": "b"}]}}
        out = enforce_array_arity.forward(data)
        assert out == data

    def test_inserts_empty_list_when_absent(self):
        data = {"reactions": {}}
        out = enforce_array_arity.forward(data)
        assert out == {"reactions": {"reaction": []}}

    def test_ignores_unknown_containers(self):
        data = {"someUnrelatedContainer": {"child": {"@a": "1"}}}
        out = enforce_array_arity.forward(data)
        assert out == data

    def test_handles_multiple_known_containers(self):
        data = {
            "reactionSuite": {
                "reactions": {"reaction": {"@label": "x"}},
                "PoPs": {"baryons": {"baryon": {"@id": "n"}}},
            }
        }
        out = enforce_array_arity.forward(data)
        assert out["reactionSuite"]["reactions"]["reaction"] == [{"@label": "x"}]
        assert out["reactionSuite"]["PoPs"]["baryons"]["baryon"] == [{"@id": "n"}]

    def test_recurses_into_list_elements(self):
        # A nested plural inside a list of plural-container occurrences.
        data = {
            "reactions": {
                "reaction": [
                    {"@label": "a", "products": {"product": {"@pid": "n"}}},
                    {"@label": "b", "products": {"product": {"@pid": "H1"}}},
                ]
            }
        }
        out = enforce_array_arity.forward(data)
        for r in out["reactions"]["reaction"]:
            assert isinstance(r["products"]["product"], list)
            assert len(r["products"]["product"]) == 1

    def test_does_not_mutate_input(self):
        data = {"reactions": {"reaction": {"@label": "x"}}}
        before = {"reactions": {"reaction": {"@label": "x"}}}
        _ = enforce_array_arity.forward(data)
        assert data == before

    def test_skips_attribute_keys(self):
        # Attribute (@-prefixed) values must never be treated as a plural
        # container even if their name happens to clash.
        data = {"node": {"@reactions": "some-attr", "real": "leaf"}}
        out = enforce_array_arity.forward(data)
        # No change — @reactions is an attribute, not a child element.
        assert out == data

    def test_skips_meta_keys(self):
        # Meta keys (_xml, _comments, _order, ...) must never be walked
        # into as if they were elements.
        data = {
            "_xml": {"version": "1.0", "encoding": "UTF-8"},
            "reactionSuite": {
                "reactions": {"reaction": {"@label": "x"}},
            },
        }
        out = enforce_array_arity.forward(data)
        # _xml is unchanged; reactions/reaction is list-wrapped.
        assert out["_xml"] == {"version": "1.0", "encoding": "UTF-8"}
        assert out["reactionSuite"]["reactions"]["reaction"] == [{"@label": "x"}]


# ===== Inverse direction =====

class TestInverse:
    def test_unwraps_singleton_list(self):
        data = {"reactions": {"reaction": [{"@label": "x"}]}}
        out = enforce_array_arity.inverse(data)
        assert out == {"reactions": {"reaction": {"@label": "x"}}}

    def test_leaves_multi_element_list_alone(self):
        data = {"reactions": {"reaction": [{"@a": "1"}, {"@a": "2"}]}}
        out = enforce_array_arity.inverse(data)
        assert out == data

    def test_removes_empty_list_key(self):
        data = {"reactions": {"reaction": []}}
        out = enforce_array_arity.inverse(data)
        assert out == {"reactions": {}}

    def test_does_not_mutate_input(self):
        data = {"reactions": {"reaction": [{"@label": "x"}]}}
        before = {"reactions": {"reaction": [{"@label": "x"}]}}
        _ = enforce_array_arity.inverse(data)
        assert data == before


# ===== Forward then inverse is identity =====

class TestRoundTrip:
    @pytest.mark.parametrize("data", [
        # Single occurrence
        {"reactions": {"reaction": {"@label": "x"}}},
        # Multi-element list
        {"reactions": {"reaction": [{"@a": "1"}, {"@a": "2"}, {"@a": "3"}]}},
        # Absent (zero occurrences)
        {"reactions": {}},
        # Mixed in same parent
        {"reactionSuite": {
            "reactions": {"reaction": {"@a": "x"}},
            "PoPs": {"baryons": {"baryon": [{"@id": "n"}, {"@id": "p"}]}},
        }},
        # Document-shape root (with _xml)
        {"_xml": {"version": "1.0", "encoding": "UTF-8"},
         "reactionSuite": {"reactions": {"reaction": {"@label": "x"}}}},
        # Nested plural inside multi-occurrence parent
        {"reactions": {"reaction": [
            {"@label": "a", "products": {"product": {"@pid": "n"}}},
            {"@label": "b", "products": {"product": [
                {"@pid": "g"}, {"@pid": "H1"}
            ]}},
        ]}},
        # Unrelated tree
        {"otherRoot": {"someChild": "leaf"}},
    ])
    def test_forward_then_inverse_is_identity(self, data):
        out = enforce_array_arity.inverse(enforce_array_arity.forward(data))
        assert out == data


# ===== Metadata sanity =====

class TestMetadata:
    def test_examples_round_trip(self):
        # The fixture examples themselves must round-trip.
        t = EnforceArrayArity()
        assert t.forward(t.example_before) == t.example_after
        assert t.inverse(t.example_after) == t.example_before

    def test_no_witness_keys_declared(self):
        # arity is dictionary-driven, not witness-driven.
        assert tuple(enforce_array_arity.witnesses_added) == ()
        assert tuple(enforce_array_arity.witnesses_consumed) == ()

    def test_dictionary_contains_expected_uniform_containers(self):
        # Spot-check a few entries we definitely expect, from the GNDS spec.
        for k in ("reactions", "products", "axes", "baryons", "nuclides"):
            assert k in UNIFORM_PLURAL_CONTAINERS
