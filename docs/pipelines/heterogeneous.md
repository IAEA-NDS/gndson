# JSON form: pipeline `heterogeneous`

Auto-generated from the transformations declared in `gndson.schema`. Do not edit by hand — regenerate with `gndson docs heterogeneous`.

## Composition

1. **`drop_heterogeneous_inner_tag`** — Collapse heterogeneous-inner plural containers to a flat list of items, each annotated with _kind: <original-inner-tag>.

## Witness flow

| Witness | Introduced by | Consumed by | Survives to end-state? |
|---|---|---|---|
| `_kind` | `drop_heterogeneous_inner_tag` | (read by inverses; not stripped on the forward path) | **yes** |

## Inverse direction

Apply transformations in reverse order: `drop_heterogeneous_inner_tag.inverse`.

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

After applying pipeline `heterogeneous`:

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

## Per-transformation reference

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
