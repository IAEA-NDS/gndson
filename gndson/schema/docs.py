"""
Auto-doc renderer for named schema pipelines.

`render_markdown(pipeline_name) -> str` produces a self-contained
markdown document describing one named pipeline. The CLI's `docs`
subcommand uses this; it can also be called directly.

What the rendered doc contains, per pipeline:

  - Title and one-line "what this pipeline does".
  - Composition: ordered list of constituent transformations + their
    one-line summaries.
  - Witness flow accounting (auto-derived from each transformation's
    `witnesses_added` / `witnesses_consumed` declarations).
  - Inverse-direction instruction.
  - End-state example: a shared canonical fixture run through the
    pipeline's forward; before/after rendered as JSON blocks.
  - Per-transformation reference: each transformation's summary,
    declared witnesses, and before/after fixture examples.

The shared `DOC_FIXTURE` is deliberately small but is crafted to
exercise every currently-defined transformation when run through
`ergonomic_split_data` — so the end-state block on each pipeline's
doc page actually demonstrates that pipeline's effect.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import List

from .pipelines import (
    PIPELINES,
    fuzzy_tags_for,
    get_pipeline,
)


# A small canonical-form fixture engineered to exercise every
# transformation currently defined in the schema layer:
#   - enforce_array_arity: reactions/reaction, baryons/baryon, axes/axis
#   - drop_uniform_inner_tag: reactions/reaction, baryons/baryon
#   - augment_kind + collapse_physicalQuantity_wrappers: mass, spin
#   - drop_heterogeneous_inner_tag: axes (axis is the only inner here,
#     but the container is treated as heterogeneous)
#   - split_whitespace_text: values
#   - expand_data_columns: data (with pipe-separated header comment)
DOC_FIXTURE = {
    "_xml": {"version": "1.0", "encoding": "UTF-8"},
    "reactionSuite": {
        "@projectile": "n",
        "@target": "H1",
        "PoPs": {
            "baryons": {"baryon": {
                "@id": "n",
                "mass": {"double": {"@label": "eval",
                                    "@value": "1.00866",
                                    "@unit": "amu"}},
                "spin": {"fraction": {"@label": "eval",
                                      "@value": "1/2"}},
            }},
        },
        "reactions": {"reaction": {
            "@label": "n + H1",
            "crossSection": {
                "XYs1d": {
                    "@label": "eval",
                    "axes": {"axis": [
                        {"@index": "1", "@label": "energy_in", "@unit": "eV"},
                        {"@index": "0", "@label": "crossSection", "@unit": "b"},
                    ]},
                    "values": "1e-5 20.4 2e7 20.4",
                },
            },
        }},
        "resonances": {"data": {
            "_text": ["\n  ", "\n  1.0 0 0.5 100 99 1\n  2.0 1 1.5 200 199 1\n"],
            "_comments": [
                "energy | L | J | totalWidth | neutronWidth | captureWidth"
            ],
            "_order": ["_text", "_comment", "_text"],
        }},
    },
}


def render_markdown(pipeline_name: str) -> str:
    """Render a markdown document for the named pipeline."""
    pipeline = get_pipeline(pipeline_name)
    out: List[str] = []
    out.append(f"# JSON form: pipeline `{pipeline_name}`")
    out.append("")
    out.append(
        "Auto-generated from the transformations declared in "
        "`gndson.schema`. Do not edit by hand — regenerate with "
        f"`gndson docs {pipeline_name}`."
    )
    out.append("")

    # ----- Composition -----
    out.append("## Composition")
    out.append("")
    if not pipeline.transformations:
        out.append("Identity pipeline — no transformations are applied; the "
                   "output JSON is the canonical form unchanged.")
    else:
        for i, t in enumerate(pipeline.transformations, start=1):
            out.append(f"{i}. **`{t.name}`** — {t.summary}")
    out.append("")

    # ----- Witness flow -----
    out.append("## Witness flow")
    out.append("")
    intro: dict = {}
    consumed: dict = {}
    for t in pipeline.transformations:
        for w in t.witnesses_added:
            intro.setdefault(w, []).append(t.name)
        for w in t.witnesses_consumed:
            consumed.setdefault(w, []).append(t.name)
    all_witnesses = sorted(set(intro) | set(consumed))
    if not all_witnesses:
        out.append("No JSON-level witnesses are introduced or consumed by "
                   "this pipeline. (Schema-layer transformations that don't "
                   "need a JSON witness keep their state in external "
                   "dictionaries; see the per-transformation reference.)")
    else:
        out.append("| Witness | Introduced by | Consumed by | Survives to end-state? |")
        out.append("|---|---|---|---|")
        for w in all_witnesses:
            introducers = ", ".join(f"`{x}`" for x in intro.get(w, [])) or "—"
            consumers = ", ".join(f"`{x}`" for x in consumed.get(w, [])) or "(read by inverses; not stripped on the forward path)"
            survives = "**yes**" if (w in intro and w not in consumed) else "no"
            out.append(f"| `{w}` | {introducers} | {consumers} | {survives} |")
    out.append("")

    # ----- Fuzzy note -----
    fuzzy_tags = fuzzy_tags_for(pipeline_name)
    if fuzzy_tags:
        tag_list = ", ".join(f"`<{t}>`" for t in sorted(fuzzy_tags))
        out.append(
            f"> **Note**: this pipeline is bijective at the GNDS-spec "
            f"level but not at the canonical-form byte level. The "
            f"round-trip normalises internal whitespace inside {tag_list} "
            f"bodies (semantically equivalent per the spec)."
        )
        out.append("")

    # ----- Inverse -----
    out.append("## Inverse direction")
    out.append("")
    if pipeline.transformations:
        names = " → ".join(
            f"`{t.name}.inverse`" for t in reversed(pipeline.transformations)
        )
        out.append(f"Apply transformations in reverse order: {names}.")
    else:
        out.append("Identity — inverse is also identity.")
    out.append("")

    # ----- End-state example -----
    out.append("## End-state example")
    out.append("")
    out.append("Sample input (canonical form):")
    out.append("")
    out.append("```json")
    out.append(json.dumps(DOC_FIXTURE, indent=2, ensure_ascii=False))
    out.append("```")
    out.append("")
    if pipeline.transformations:
        out.append(f"After applying pipeline `{pipeline_name}`:")
    else:
        out.append(f"After applying pipeline `{pipeline_name}` (identity, "
                   f"so output equals input):")
    out.append("")
    out.append("```json")
    rendered = pipeline.forward(deepcopy(DOC_FIXTURE))
    out.append(json.dumps(rendered, indent=2, ensure_ascii=False))
    out.append("```")
    out.append("")

    # ----- Per-transformation reference -----
    if pipeline.transformations:
        out.append("## Per-transformation reference")
        out.append("")
        for t in pipeline.transformations:
            out.append(f"### `{t.name}`")
            out.append("")
            out.append(t.summary)
            out.append("")
            if t.witnesses_added:
                out.append(
                    f"**Witnesses introduced:** "
                    + ", ".join(f"`{w}`" for w in t.witnesses_added)
                )
            if t.witnesses_consumed:
                out.append(
                    f"**Witnesses consumed:** "
                    + ", ".join(f"`{w}`" for w in t.witnesses_consumed)
                )
            if t.witnesses_added or t.witnesses_consumed:
                out.append("")
            out.append("**Before:**")
            out.append("")
            out.append("```json")
            out.append(json.dumps(t.example_before, indent=2, ensure_ascii=False))
            out.append("```")
            out.append("")
            out.append("**After:**")
            out.append("")
            out.append("```json")
            out.append(json.dumps(t.example_after, indent=2, ensure_ascii=False))
            out.append("```")
            out.append("")
    return "\n".join(out)


def render_all_markdown():
    """Yield `(pipeline_name, markdown_text)` for every named pipeline."""
    for name in PIPELINES:
        yield name, render_markdown(name)
