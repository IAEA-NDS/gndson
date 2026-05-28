# JSON form: pipeline `data_columns`

Auto-generated from the transformations declared in `gndson.schema`. Do not edit by hand — regenerate with `gndson docs data_columns`.

## Composition

1. **`expand_data_columns`** — Heuristic augmentation: parse <data> elements' pipe-separated header comments into _columns and group the text body into _rows (list of lists of token strings).

## Witness flow

| Witness | Introduced by | Consumed by | Survives to end-state? |
|---|---|---|---|
| `_columns` | `expand_data_columns` | (read by inverses; not stripped on the forward path) | **yes** |
| `_rows` | `expand_data_columns` | (read by inverses; not stripped on the forward path) | **yes** |

## Inverse direction

Apply transformations in reverse order: `expand_data_columns.inverse`.

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

After applying pipeline `data_columns`:

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
        ],
        "_columns": [
          "energy",
          "L",
          "J",
          "totalWidth",
          "neutronWidth",
          "captureWidth"
        ],
        "_rows": [
          [
            "1.0",
            "0",
            "0.5",
            "100",
            "99",
            "1"
          ],
          [
            "2.0",
            "1",
            "1.5",
            "200",
            "199",
            "1"
          ]
        ]
      }
    }
  }
}
```

## Per-transformation reference

### `expand_data_columns`

Heuristic augmentation: parse <data> elements' pipe-separated header comments into _columns and group the text body into _rows (list of lists of token strings).

**Witnesses introduced:** `_columns`, `_rows`

**Before:**

```json
{
  "data": {
    "_text": [
      "\n  ",
      "\n  1 2 3\n  4 5 6\n"
    ],
    "_comments": [
      "a | b | c"
    ],
    "_order": [
      "_text",
      "_comment",
      "_text"
    ]
  }
}
```

**After:**

```json
{
  "data": {
    "_text": [
      "\n  ",
      "\n  1 2 3\n  4 5 6\n"
    ],
    "_comments": [
      "a | b | c"
    ],
    "_order": [
      "_text",
      "_comment",
      "_text"
    ],
    "_columns": [
      "a",
      "b",
      "c"
    ],
    "_rows": [
      [
        "1",
        "2",
        "3"
      ],
      [
        "4",
        "5",
        "6"
      ]
    ]
  }
}
```
