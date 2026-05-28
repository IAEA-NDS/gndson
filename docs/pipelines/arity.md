# JSON form: pipeline `arity`

Auto-generated from the transformations declared in `gndson.schema`. Do not edit by hand — regenerate with `gndson docs arity`.

## Composition

1. **`enforce_array_arity`** — For known plural containers, ensure the named inner child is always a JSON list (wrap scalars, insert [] when absent).

## Witness flow

No JSON-level witnesses are introduced or consumed by this pipeline. (Schema-layer transformations that don't need a JSON witness keep their state in external dictionaries; see the per-transformation reference.)

## Inverse direction

Apply transformations in reverse order: `enforce_array_arity.inverse`.

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

After applying pipeline `arity`:

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
        "baryon": [
          {
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
        ]
      }
    },
    "reactions": {
      "reaction": [
        {
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
      ]
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
