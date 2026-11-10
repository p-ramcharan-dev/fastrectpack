| Workload | Rectangles | Bins used | Original rectpack | Pure-Python fixes | fastrectpack (C++) | Speedup, fixes | Speedup, C++ | Output identical |
|---|---|---|---|---|---|---|---|---|
| random | 200 | 1 | 0.344 s | 0.114 s | 0.0032 s | 3.0x | 106.1x | yes |
| random | 500 | 2 | 0.948 s | 0.172 s | 0.0057 s | 5.5x | 164.9x | yes |
| random | 1,000 | 4 | 3.525 s | 0.475 s | 0.0144 s | 7.4x | 245.6x | yes |
| random | 2,000 | 7 | 9.286 s | 1.071 s | 0.0795 s | 8.7x | 116.8x | yes |
| random | 5,000 | 16 | 34.159 s | 7.820 s | 0.1364 s | 4.4x | 250.4x | yes |
| cutting | 500 | 27 | 0.036 s | 0.022 s | 0.0068 s | 1.7x | 5.3x | yes |
| cutting | 1,000 | 50 | 0.119 s | 0.066 s | 0.0221 s | 1.8x | 5.4x | yes |
| cutting | 2,000 | 100 | 0.415 s | 0.214 s | 0.0780 s | 1.9x | 5.3x | yes |
| sprites | 500 | 2 | 0.158 s | 0.072 s | 0.0061 s | 2.2x | 25.9x | yes |
| sprites | 1,000 | 3 | 1.111 s | 0.295 s | 0.0162 s | 3.8x | 68.7x | yes |
| sprites | 2,000 | 5 | 3.394 s | 0.737 s | 0.0385 s | 4.6x | 88.1x | yes |
| skewed | 500 | 3 | 0.684 s | 0.120 s | 0.0048 s | 5.7x | 141.1x | yes |
| skewed | 1,000 | 4 | 2.984 s | 0.243 s | 0.0102 s | 12.3x | 292.1x | yes |
| skewed | 2,000 | 11 | 2.197 s | 0.483 s | 0.0270 s | 4.5x | 81.5x | yes |
