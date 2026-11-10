| Input | Rectangles | Original rectpack | fastrectpack (C++) | Speedup | Speedup range across rounds | Output identical, types included |
|---|---|---|---|---|---|---|
| int rectangles, `numpy.float64` bin (gdsfactory) | 100 | 0.031 s | 0.0006 s | 55x | 47x to 57x | yes |
| `float` rectangles and bin | 100 | 0.027 s | 0.0006 s | 46x | 40x to 50x | yes |
| `numpy.int64` rectangles, int bin | 100 | 0.039 s | 0.0007 s | 56x | 51x to 60x | yes |
| int rectangles, `numpy.float64` bin (gdsfactory) | 300 | 0.633 s | 0.0022 s | 284x | 247x to 286x | yes |
| `float` rectangles and bin | 300 | 0.592 s | 0.0023 s | 257x | 224x to 262x | yes |
| `numpy.int64` rectangles, int bin | 300 | 0.840 s | 0.0027 s | 314x | 263x to 321x | yes |
| int rectangles, `numpy.float64` bin (gdsfactory) | 1,000 | 20.612 s | 0.0173 s | 1193x | 1184x to 1208x | yes |
| `float` rectangles and bin | 1,000 | 20.272 s | 0.0148 s | 1374x | 1063x to 1387x | yes |
| `numpy.int64` rectangles, int bin | 1,000 | 27.063 s | 0.0156 s | 1734x | 1438x to 1734x | yes |
