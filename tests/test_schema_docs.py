"""Unit tests for `gndson.schema.docs.render_markdown`."""

import pytest

from gndson.schema.docs import (
    DOC_FIXTURE,
    render_all_markdown,
    render_markdown,
)
from gndson.schema.pipelines import (
    FUZZY_PIPELINES,
    PIPELINES,
    pipeline_names,
)


# ===== Smoke tests for every pipeline =====


@pytest.mark.parametrize("name", pipeline_names())
def test_render_each_pipeline_does_not_crash(name):
    md = render_markdown(name)
    assert isinstance(md, str)
    assert len(md) > 0


@pytest.mark.parametrize("name", pipeline_names())
def test_render_each_pipeline_has_required_sections(name):
    md = render_markdown(name)
    assert f"# JSON form: pipeline `{name}`" in md
    assert "## Composition" in md
    assert "## Witness flow" in md
    assert "## Inverse direction" in md
    assert "## End-state example" in md


@pytest.mark.parametrize("name", pipeline_names())
def test_per_transformation_section_for_non_empty_pipelines(name):
    md = render_markdown(name)
    pipeline = PIPELINES[name]
    if pipeline.transformations:
        assert "## Per-transformation reference" in md
        for t in pipeline.transformations:
            assert f"### `{t.name}`" in md


# ===== Witness flow accounting =====


def test_witness_table_records_kind_for_ergonomic():
    md = render_markdown("ergonomic")
    # ergonomic includes augment_kind which adds _kind. Inverse not consumed.
    assert "`_kind`" in md
    assert "`augment_kind`" in md


def test_fuzzy_pipeline_emits_note():
    md = render_markdown("ergonomic_split")
    assert "GNDS-spec level" in md or "spec-level" in md


def test_non_fuzzy_pipeline_has_no_fuzzy_note():
    md = render_markdown("ergonomic")
    assert "GNDS-spec level" not in md


# ===== End-state example actually shows the pipeline's effect =====


def test_end_state_example_shows_post_transformation():
    """For ergonomic_split_data, the end-state example should differ from
    the canonical fixture in observable ways: collapsed wrappers, list
    arity, _kind annotations, etc."""
    md = render_markdown("ergonomic_split_data")
    # The post-transformation block follows the input block. Both are JSON.
    # We verify a few signals that the pipeline ran:
    assert '"_kind"' in md     # augment_kind + collapse contributes _kind
    assert '"_columns"' in md  # expand_data_columns contributes _columns
    assert '"_rows"' in md     # expand_data_columns contributes _rows


def test_identity_pipeline_renders():
    md = render_markdown("canonical")
    assert "Identity pipeline" in md or "identity" in md.lower()


# ===== render_all_markdown =====


def test_render_all_emits_one_doc_per_pipeline():
    docs = list(render_all_markdown())
    names = [n for n, _ in docs]
    assert set(names) == set(pipeline_names())
    for _, md in docs:
        assert isinstance(md, str)
        assert len(md) > 0


# ===== Fixture is valid =====


def test_fixture_round_trips_through_every_pipeline():
    """The shared DOC_FIXTURE should be valid canonical-form input that
    every pipeline can apply forward + inverse to. (Same property the
    corpus driver verifies, applied here to the one shared fixture.)"""
    from gndson.schema.pipelines import normalise_for_fuzzy_compare
    for name, pipeline in PIPELINES.items():
        out = pipeline.inverse(pipeline.forward(DOC_FIXTURE))
        fuzzy_tags = FUZZY_PIPELINES.get(name)
        if fuzzy_tags is not None:
            a = normalise_for_fuzzy_compare(DOC_FIXTURE, fuzzy_tags)
            b = normalise_for_fuzzy_compare(out, fuzzy_tags)
            assert a == b, f"pipeline {name!r} broke the doc fixture (fuzzy)"
        else:
            assert out == DOC_FIXTURE, f"pipeline {name!r} broke the doc fixture"
