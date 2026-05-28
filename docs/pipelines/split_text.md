# JSON form: pipeline `split_text`

Auto-generated from the transformations declared in `gndson.schema`. Do not edit by hand — regenerate with `gndson docs split_text`.

## Composition

1. **`split_whitespace_text`** — Split text-only elements whose body is a whitespace-separated list into JSON lists of token strings. Bijective at the GNDS-spec level (internal whitespace is normalised).

## Witness flow

No JSON-level witnesses are introduced or consumed by this pipeline. (Schema-layer transformations that don't need a JSON witness keep their state in external dictionaries; see the per-transformation reference.)

> **Note**: this pipeline is bijective at the GNDS-spec level but not at the canonical-form byte level. The round-trip normalises internal whitespace inside `<values>` bodies (semantically equivalent per the spec).

## Inverse direction

Apply transformations in reverse order: `split_whitespace_text.inverse`.

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

After applying pipeline `split_text`:

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
            "values": [
              "1e-5",
              "20.4",
              "2e7",
              "20.4"
            ]
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
