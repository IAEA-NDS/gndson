# JSON form: pipeline `ergonomic_split`

Auto-generated from the transformations declared in `gndson.schema`. Do not edit by hand — regenerate with `gndson docs ergonomic_split`.

## Composition

1. **`enforce_array_arity`** — For known plural containers, ensure the named inner child is always a JSON list (wrap scalars, insert [] when absent).
2. **`drop_uniform_inner_tag`** — Collapse plural containers with one known inner tag: {Xs: {X: [list]}} -> {Xs: [list]}. Skipped when the container has comments or other meta keys.
3. **`augment_kind`** — For each physicalQuantityNode wrapper with exactly one element child (no attributes, no meta keys), annotate it with _kind: <inner-tag>.
4. **`collapse_physicalQuantity_wrappers`** — For each element carrying _kind, hoist the matching inner child's attributes and sub-children onto the wrapper; the inverse re-creates the inner child using _kind.
5. **`drop_heterogeneous_inner_tag`** — Collapse heterogeneous-inner plural containers to a flat list of items, each annotated with _kind: <original-inner-tag>.
6. **`split_whitespace_text`** — Split text-only elements whose body is a whitespace-separated list into JSON lists of token strings. Bijective at the GNDS-spec level (internal whitespace is normalised).

## Witness flow

| Witness | Introduced by | Consumed by | Survives to end-state? |
|---|---|---|---|
| `_kind` | `augment_kind`, `drop_heterogeneous_inner_tag` | (read by inverses; not stripped on the forward path) | **yes** |

> **Note**: this pipeline is bijective at the GNDS-spec level but not at the canonical-form byte level. The round-trip normalises internal whitespace inside `<values>` bodies (semantically equivalent per the spec).

## Inverse direction

Apply transformations in reverse order: `split_whitespace_text.inverse` → `drop_heterogeneous_inner_tag.inverse` → `collapse_physicalQuantity_wrappers.inverse` → `augment_kind.inverse` → `drop_uniform_inner_tag.inverse` → `enforce_array_arity.inverse`.

## End-state example

Sample input (canonical form):

```json
{
  "_xml": {
    "version": "1.0",
    "encoding": "UTF-8"
  },
  "reactionSuite": {
    "@projectile": "n",
    "@target": "H1",
    "PoPs": {
      "baryons": {
        "baryon": {
          "@id": "n",
          "mass": {
            "double": {
              "@label": "eval",
              "@value": "1.00866",
              "@unit": "amu"
            }
          },
          "spin": {
            "fraction": {
              "@label": "eval",
              "@value": "1/2"
            }
          }
        }
      }
    },
    "reactions": {
      "reaction": {
        "@label": "n + H1",
        "crossSection": {
          "XYs1d": {
            "@label": "eval",
            "axes": {
              "axis": [
                {
                  "@index": "1",
                  "@label": "energy_in",
                  "@unit": "eV"
                },
                {
                  "@index": "0",
                  "@label": "crossSection",
                  "@unit": "b"
                }
              ]
            },
            "values": "1e-5 20.4 2e7 20.4"
          }
        }
      }
    },
    "resonances": {
      "data": {
        "_text": [
          "\n  ",
          "\n  1.0 0 0.5 100 99 1\n  2.0 1 1.5 200 199 1\n"
        ],
        "_comments": [
          "energy | L | J | totalWidth | neutronWidth | captureWidth"
        ],
        "_order": [
          "_text",
          "_comment",
          "_text"
        ]
      }
    }
  }
}
```

After applying pipeline `ergonomic_split`:

```json
{
  "_xml": {
    "version": "1.0",
    "encoding": "UTF-8"
  },
  "reactionSuite": {
    "@projectile": "n",
    "@target": "H1",
    "PoPs": {
      "baryons": [
        {
          "@id": "n",
          "mass": {
            "_kind": "double",
            "@label": "eval",
            "@value": "1.00866",
            "@unit": "amu"
          },
          "spin": {
            "_kind": "fraction",
            "@label": "eval",
            "@value": "1/2"
          }
        }
      ]
    },
    "reactions": [
      {
        "@label": "n + H1",
        "crossSection": {
          "XYs1d": {
            "@label": "eval",
            "axes": [
              {
                "@index": "1",
                "@label": "energy_in",
                "@unit": "eV",
                "_kind": "axis"
              },
              {
                "@index": "0",
                "@label": "crossSection",
                "@unit": "b",
                "_kind": "axis"
              }
            ],
            "values": [
              "1e-5",
              "20.4",
              "2e7",
              "20.4"
            ]
          }
        }
      }
    ],
    "resonances": {
      "data": {
        "_text": [
          "\n  ",
          "\n  1.0 0 0.5 100 99 1\n  2.0 1 1.5 200 199 1\n"
        ],
        "_comments": [
          "energy | L | J | totalWidth | neutronWidth | captureWidth"
        ],
        "_order": [
          "_text",
          "_comment",
          "_text"
        ]
      }
    }
  }
}
```

## Per-transformation reference

### `enforce_array_arity`

For known plural containers, ensure the named inner child is always a JSON list (wrap scalars, insert [] when absent).

**Before:**

```json
{
  "reactions": {
    "reaction": {
      "@label": "n + H1"
    }
  },
  "products": {}
}
```

**After:**

```json
{
  "reactions": {
    "reaction": [
      {
        "@label": "n + H1"
      }
    ]
  },
  "products": {
    "product": []
  }
}
```

### `drop_uniform_inner_tag`

Collapse plural containers with one known inner tag: {Xs: {X: [list]}} -> {Xs: [list]}. Skipped when the container has comments or other meta keys.

**Before:**

```json
{
  "reactions": {
    "reaction": [
      {
        "@label": "a"
      },
      {
        "@label": "b"
      }
    ]
  },
  "products": {
    "product": []
  }
}
```

**After:**

```json
{
  "reactions": [
    {
      "@label": "a"
    },
    {
      "@label": "b"
    }
  ],
  "products": []
}
```

### `augment_kind`

For each physicalQuantityNode wrapper with exactly one element child (no attributes, no meta keys), annotate it with _kind: <inner-tag>.

**Witnesses introduced:** `_kind`

**Before:**

```json
{
  "mass": {
    "double": {
      "@label": "eval",
      "@value": "1.0",
      "@unit": "amu"
    }
  }
}
```

**After:**

```json
{
  "mass": {
    "_kind": "double",
    "double": {
      "@label": "eval",
      "@value": "1.0",
      "@unit": "amu"
    }
  }
}
```

### `collapse_physicalQuantity_wrappers`

For each element carrying _kind, hoist the matching inner child's attributes and sub-children onto the wrapper; the inverse re-creates the inner child using _kind.

**Before:**

```json
{
  "mass": {
    "_kind": "double",
    "double": {
      "@label": "eval",
      "@value": "1.0",
      "@unit": "amu"
    }
  }
}
```

**After:**

```json
{
  "mass": {
    "_kind": "double",
    "@label": "eval",
    "@value": "1.0",
    "@unit": "amu"
  }
}
```

### `drop_heterogeneous_inner_tag`

Collapse heterogeneous-inner plural containers to a flat list of items, each annotated with _kind: <original-inner-tag>.

**Witnesses introduced:** `_kind`

**Before:**

```json
{
  "function1ds": {
    "XYs1d": [
      {
        "@index": "0"
      },
      {
        "@index": "1"
      }
    ],
    "regions1d": {
      "@a": "x"
    }
  }
}
```

**After:**

```json
{
  "function1ds": [
    {
      "_kind": "XYs1d",
      "@index": "0"
    },
    {
      "_kind": "XYs1d",
      "@index": "1"
    },
    {
      "_kind": "regions1d",
      "@a": "x"
    }
  ]
}
```

### `split_whitespace_text`

Split text-only elements whose body is a whitespace-separated list into JSON lists of token strings. Bijective at the GNDS-spec level (internal whitespace is normalised).

**Before:**

```json
{
  "values": "1.0 2.0 3.0"
}
```

**After:**

```json
{
  "values": [
    "1.0",
    "2.0",
    "3.0"
  ]
}
```
