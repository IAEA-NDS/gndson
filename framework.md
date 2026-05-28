# Framework: operations, witnesses, and the round-trip oracle

This document captures the design discipline that gndson is built on. It
applies to any scientific-database modernization where you transform data
between representations and need to be sure no information is lost without
intending to lose it. The framework is the basis for design decisions in this
repo (e.g., why the canonical form looks the way it does, why some features
are deliberately *not* implemented at the translator level).

All "GNDS PDF" / "GNDS 2.1 spec" references throughout this document refer to:
> Mattoon, C., Gert, G., Holcomb, A., Brown, D., Wiarda, D., Chapman, C.,
> Haeck, W., Staley, M. (2025). *GNDS-2.1 Specifications.* NEA Working
> Paper NEA/WKP(2025)6, Nuclear Energy Agency, OECD.

The premise is one sentence:

> A modernization is trustworthy only if a machine can check it.

The framework is what makes "the machine can check it" mean something
specific.

## The three operations

Every data-shape change between two representations falls into one of three
categories. The distinction matters because it determines what is checkable.

### Transformation

Restructure the data without changing the information it carries. A
transformation is **information-capacity-preserving** and admits an
inverse: there is a bijection between the input and output.

```text
{"EN": [1, 2, 3], "DATA": [5, 6, 7]}
        ↕  bijection
[{"EN": 1, "DATA": 5}, {"EN": 2, "DATA": 6}, {"EN": 3, "DATA": 7}]
```

The two forms encode the same information; you can move freely between them.

### Augmentation

Add information to the data from an external source (e.g., a dictionary
lookup), without removing anything that was there.

```text
{"FACILITY": "(NGEN)"}
        ↓  + dictionary {NGEN: "Neutron Generator"}
{"FACILITY": "(NGEN)", "FACILITY-expanded": "Neutron Generator"}
```

The augmented form contains the original (verbatim) plus new keys that are
derivable from the original via the dictionary. **Augmentations are
trivially reversible** by removing the added keys.

### Reduction

Remove information. This is the *only* fundamentally lossy operation of the
three.

```text
{"FACILITY": "(NGEN)", "FACILITY-expanded": "Neutron Generator"}
        ↓  reduction
{"FACILITY": "(NGEN)"}
```

Reductions cannot be reversed without an external source of the lost
information.

## Information capacity is the real axis

The three categories cluster around one binary distinction:

| Operation       | Information capacity | Reversible? |
|-----------------|----------------------|-------------|
| transformation  | preserved            | yes, bijection |
| augmentation    | increased (derivably) | yes, by removal |
| reduction       | decreased            | not without external help |

The first two are **capacity-preserving** in a strong sense: they admit a
mechanical inverse. Reductions are the only ones that genuinely commit you
to a loss.

## Witnesses make would-be-reductions reversible

A common need: re-express data in a different shape that *would* lose
information unless you stash the lost bit somewhere. Stashing it is called
adding a **witness**.

```text
{"DATA": 1, "UNIT": "B"}                  # 1 barn
        ↓  unit standardization
{"DATA": 1000, "UNIT": "MB"}              # 1000 millibarn — same physics, but
                                            UNIT field permanently changed
                                            (reduction in the trivial sense
                                            that we can't recover the original
                                            UNIT spelling from the result)
        ↕  with witness
{"DATA": 1000, "UNIT": "MB", "OLD-UNIT": "B"}  # bijective again
```

A reduction *with* a witness is a transformation. The discipline is to
**identify reductions explicitly and add the witness rather than letting
them happen silently**.

## The recipe

The four steps that follow from the above:

1. **If a transformation would lose information, add a witness first.**
   Convert the implicit reduction into an explicit transformation by
   recording what would otherwise vanish.
2. **Validate by round-tripping the entire library**:
   `inverse(transform(x)) == x for all x in library`.
   This is the oracle. It catches both bugs in the transformation
   implementation and structurally inconsistent entries in the library
   itself.
3. **Defer reduction as long as possible.** A genuine reduction (with no
   meaningful witness) is a user-facing export choice, not something the
   transformation pipeline does on its own.
4. **Keep the witness as long as possible.** The downstream consumer can
   decide whether to drop it; the producer should not preempt that choice.

## Composition

Real pipelines combine the three operations. A typical chain might be:

```text
text  --transform-->  JSON  --augment[dict]-->  JSON'  --transform-->  JSON''  --reduce-->  JSON'''
└─────────────── capacity-preserving (reversible) ──────────────┘  └─ user export ─┘
```

Everything up to `JSON''` is bijective: you can reconstruct `text` from
`JSON''` if you have the dictionary. The final `JSON'''` step (the
reduction) is the one that commits to loss. Round-trip oracles validate the
left segment; the right segment is documented and intentional.

## What the round-trip oracle unlocks

- **High-confidence assertion that a transformation is correctly
  implemented.** If round-trip passes on every entry, the transformation
  preserves what it claims to preserve.
- **Identification of structurally inconsistent entries** in the source
  library. When round-trip fails on a specific file, it often points to a
  defect in *that file*, not the transformation.
- **Fast iteration.** Bugs are localized to the entries that newly fail.
- **Agentic / LLM-assisted development.** The human review bottleneck for
  "did this change preserve meaning" is replaced by a computational search
  problem: "does the round-trip still hold on the corpus?".

## What the framework does NOT solve

Stating this up front matters for honesty:

- **Choosing a meaningful and pertinent ontology.** The framework checks
  preservation, not aptness. A round-trippable bad shape is still a bad
  shape.
- **Deciding the optimal target structure.** Same.
- **Floating-point round-trip exactness.** Bit-equality on floats requires
  preserving source string representations or accepting fuzzy comparison.
- **Whether the transformation means what you intended.** Round-trip
  checks preservation, not intent. A bug in your spec is invisible to it.

## Formal properties (for the augmentation case)

For an augmentation `augment(x, dict)`:

```text
Recoverability:        reduce(augment(x, dict)) == x
Consistency invariant: augment(x, dict)[expanded_key] == dict[x[abbreviation_key]]
Idempotence:           augment(augment(x, dict), dict) == augment(x, dict)
```

Recoverability is the round-trip oracle. Consistency invariant is what
"derivable from external source" means. Idempotence is what makes the
augmentation safe to re-run.

## How gndson uses this

The translator in this repo is exactly one transformation:
**GNDS XML ↔ canonical JSON**, both directions bijective up to the
non-encoding-whitespace equivalences listed in `spec.md` §9. The corpus
round-trip test is the oracle (`tests/test_roundtrip_corpus.py` — currently
145/145 spec-equivalent, 145/145 byte-form-strict).

Two design decisions follow directly from the framework:

1. **The canonical JSON form is deliberately wrapper-faithful.** Patterns
   like `<mass><double @value="..."/></mass>` come out as nested objects,
   not flattened. The schema knowledge that would let us collapse them is
   not available to the translator, so any flattening would be a *silent
   reduction* — discarding the `double` type tag has no inverse without
   external help. Collapsing belongs to a higher layer that can carry the
   witness (or in a user-facing export that accepts the loss).

2. **`_arrays` was rejected after considering it.** A schema-driven
   "always array" hint cannot survive the XML hop (both `<x/>` and the
   bracketed-list form re-emit identically), so storing it in the JSON
   would be either redundant (in the simple cases) or a non-bijective
   witness (in the round-trip-back-to-XML case). The translator stays
   honest about what XML reproduces by itself.

If schema knowledge is incorporated in the future, it should be **a layer
above the translator**, not inside it:

```text
gndson/
  parser.py        # XML → JSON      (transformation, bottom of stack)
  serializer.py    # JSON → XML      (inverse)
  schema/
    augment.py     # JSON → JSON'    (adds derivable schema info, never removes)
    transform.py   # JSON' → JSON''  (collapses wrappers using augmented info
                                       as witness; bijective)
    reduce.py      # JSON'' → JSON''' (drops witnesses; user-facing export only)
```

Each new layer gets its own corpus-wide round-trip test, modelled on the
existing one. A change is accepted as a transformation only when round-trip
passes across the corpus.

## Transformation library and auto-documentation

This section applies to the layers above the bottom translator
(`gndson/schema/*` in the architecture sketch above). The bottom translator
itself is fixed; everything else is built as a library of small, composable
transformations.

### Each transformation is a self-contained unit

A transformation in the library carries fixed metadata:

- `name` — short identifier (e.g. `collapse_physicalQuantity_wrappers`).
- `summary` — one-line description of what it does.
- `applies_to` — predicate or spec citation defining which nodes it touches.
- `witnesses_added` — list of `_*` keys it introduces in the forward direction.
- `witnesses_consumed` — list of keys it removes in the forward direction
  (typically empty for augmentations, populated for transformations that
  use a prior augmentation as their witness).
- `example_before` — a small JSON snippet showing a typical input shape.
- `example_after` — the corresponding output snippet.
- `forward(node, ctx)` — the forward function.
- `inverse(node, ctx)` — the inverse.

The before/after examples are **testable fixtures**: the test suite asserts
`forward(example_before) == example_after` and `inverse(example_after) ==
example_before`. A stale example breaks the build.

### Pipelines are explicit ordered lists

A consumer assembles a named pipeline by naming the transformations and
their order:

```python
PHYSICS_FRIENDLY = Pipeline([
    augment_kind,
    collapse_physicalQuantity_wrappers,
    coerce_numbers,
])
```

Each pipeline gets its own corpus-wide round-trip test. A pipeline is
accepted as a transformation only after passing that check across the full
corpus. Different consumer audiences (display-oriented vs. analysis-oriented)
get different named pipelines, all built from the same bottom layer and the
same library.

### Auto-documentation is end-state focused

The doc generator produces a derived spec describing **what the JSON looks
like at the end of the pipeline**, not a step-by-step chain narration. Each
transformation contributes one section keyed by the element class it
touches:

```markdown
# JSON form — pipeline "physics-friendly"

## Final shape examples
- A `mass` element appears as:
    {"_kind": "double", "@label": "eval", "@value": "1.0", "@unit": "amu"}
  Contributed by: collapse_physicalQuantity_wrappers

- A `reaction` slot always appears as a list, even with one element.
  Contributed by: always_array_enforcement

## Witnesses preserved in the JSON
- _kind — introduced by collapse_physicalQuantity_wrappers, required by its inverse.

## Inverse direction
Apply transformations in reverse order:
coerce_numbers.inverse → collapse_physicalQuantity_wrappers.inverse → augment_kind.inverse.
```

No chain narration: the reader sees the final shape and a one-line
attribution per element class. The local before/after examples on each
transformation are used for testing and for understanding the transformation
in isolation, not for the end-user spec.

### Chain handling: witness flow accounting

When transformations consume each other's witnesses (A introduces `_kind`,
a later B uses then discards it), composition is handled by *witness flow
accounting* — a static analysis of the pipeline's metadata, not a
derivation:

- For each witness key `_x`, track which transformation introduces it and
  which (if any) consumes it.
- If introduced and never consumed → it survives to the final JSON;
  document it.
- If introduced and consumed by a later transformation → internal artifact;
  omit from end-state docs.
- If consumed but never introduced → pipeline ordering error; the doc
  generator (and the test runner) should refuse.

This is aggregation, not state-machine reasoning, so the doc stays compact
no matter how long the pipeline becomes.

### Design rule: transformations should be locally meaningful

If a transformation's behavior only makes sense given chain context that
precedes it (e.g. "this only works after `coerce_numbers` has run"), it is
wrong-sized and should be split. A reader should be able to look at one
transformation's metadata and understand both its forward and its inverse
without tracing the pipeline. The auto-doc tooling will surface this kind
of pain early: a transformation whose `example_before` reflects a
non-canonical intermediate shape is a tell.

### Practical scale expectation

The architecture can in principle support arbitrarily deep pipelines, but
the GNDS scope suggests modesty:

- Around 5–8 transformations total in the library (physicalQuantity
  wrapper collapse; labelNode polymorphic collapse for
  `crossSection`/`multiplicity`; always-array enforcement; `href` inlining;
  number coercion; unit expansion; default-attribute omission).
- Most are orthogonal — they touch different parts of the JSON.
- Real chains are 2 deep in 2–3 places
  (collapse → coerce_numbers; collapse → expand_units;
  inline_href → cross-section operations).

A combinatorial pipeline graph is not anticipated. If it materializes
later, that is a re-think opportunity, not something to design for now.

## First-cut schema-layer build order

Concrete plan for the initial transformation library, in suggested
implementation order. Each step is testable in isolation via its own
corpus-wide round-trip and reuses infrastructure or dictionaries built
by earlier steps.

### 1. `enforce_array_arity`

Always-list discipline for plural-named containers. A curated dictionary
maps tag names (`reactions`, `products`, `axes`, ...) to their multiplicity
class. Forward: if a container's child key is in the always-list set,
ensure its value is a JSON list — wrap a scalar in a 1-element list, emit
`[]` for zero occurrences. Inverse: trust the JSON shape (the dictionary
is the source of truth at both ends).

- Witness: none in the JSON.
- Scope: all known plural containers, regardless of inner type.
- Why first: simplest exercise of the schema-layer infrastructure (no
  per-element schema check, no fallback case, no JSON witness). Builds
  the `Transformation` base class and the corpus test harness.

### 2. `drop_uniform_inner_tag`

For plural containers whose inner element is a single known tag
(`reactions/reaction`, `products/product`, `axes/axis`,
`baryons/baryon`, ...), collapse the redundant inner key:
`{Xs: [obj1, obj2]}` instead of `{Xs: {X: [obj1, obj2]}}`. Inverse:
re-wrap using the inner tag name fetched from the same dictionary.

- Witness: none in the JSON.
- Scope: the uniform-inner subset of the plural-container dictionary.
- Why second: biggest ergonomic win for downstream consumers; reuses
  the dictionary from step 1 (one more column in the same table); still
  no JSON-level witness needed.

### 3. `augment_kind` + `collapse_physicalQuantity_wrappers`

A pair of transformations targeting the GNDS `physicalQuantityNode`
abstract class. `augment_kind` annotates eligible wrappers with
`_kind: <inner-tag>` (e.g. `_kind: "double"`); the collapse hoists the
inner child's attributes onto the wrapper and uses `_kind` as the
witness to invert.

- Witness: `_kind`, per-element. Survives in the end-state JSON.
- Scope: 10 spec-defined wrappers (mass, charge, spin, parity, halflife,
  energy, Q, probability, plus reaction-data mass/energy). Falls back
  to no-collapse for wrappers with multiple children (style-labelled
  alternates) or unexpected attributes.
- Why third: introduces the witness mechanism and exercises pipeline
  composition with a real (augment → collapse) chain. The witness flow
  accounting in the auto-doc gets its first real test here.

### 4. `drop_heterogeneous_inner_tag` (opt-in)

For plural containers whose inner element can be one of several types
(`function1ds` → {`XYs1d`, `regions1d`, `constant1d`, ...},
`distribution` → {`angularTwoBody`, `isotropic2d`, ...}, `styles`,
`sums`, ...), collapse to a list of objects each carrying `_kind` — the
same witness as in step 3.

- Witness: `_kind`, per-element. Same mechanism as step 3.
- Scope: the heterogeneous-inner subset of the plural-container
  dictionary.
- Why fourth: reuses the `_kind` machinery from step 3; opt-in because
  some consumers prefer the inner tag name visible as the key rather
  than tucked under `_kind`.

### Recommended default pipeline

After all four steps land:

```python
ERGONOMIC = Pipeline([
    enforce_array_arity,
    drop_uniform_inner_tag,
    augment_kind,
    collapse_physicalQuantity_wrappers,
    # drop_heterogeneous_inner_tag,  # opt-in
])
```

Each pipeline gets its own corpus-wide round-trip test. Steps 1–4 are
orthogonal in the witness sense (only step 3 introduces and uses a JSON
witness; the others are external-dictionary transformations), so the
pipeline order is essentially free — convention puts augmentations
before their consumers and the independent steps near the front.

## Heuristic checklist for new features

When considering a feature that changes the JSON form, ask:

1. Does the proposed change preserve information capacity, or remove some?
2. If it removes information, what is the witness, and where is it kept?
3. Is the inverse implementable, given only the new form and the witness?
4. Does it round-trip across the entire corpus?
5. If it doesn't, is that intentional (i.e., is the feature a user-facing
   reduction), and is it documented as such?

If you can answer 1–4 with "yes / clearly / yes / yes" and the corpus test
passes, the feature is a transformation. If you have to answer 5 with
"yes", it's a reduction and should be opt-in for export, not part of the
canonical pipeline.

## Pointers

- The corpus round-trip oracle: `tests/test_roundtrip_corpus.py`.
- The translator's canonical-form definition: `spec.md`.
- The XML-equivalence comparator that the round-trip relies on:
  `gndson/_compare.py`.
