# Case study: a packing job from 21 seconds to 0.14 seconds, with identical results

**Outcome.** Packing 5,000 rectangles with the open-source `rectpack` library took 21.1 seconds. After this work it takes 0.14 seconds, 155 times faster, and the output is the same down to every coordinate. Across 14 test workloads the speedup ranged from 5x to 246x.

## The problem

`rectpack` is a Python library that arranges rectangles into bins. Businesses use this kind of code to lay out parts on sheets of wood or metal before cutting, to build image atlases for games, and to arrange labels or print jobs. The library is downloaded several hundred thousand times a month.

It is written entirely in Python, and it gets slow quickly as jobs grow. Its own documentation tells users to switch to a lower-quality method "unless the packing is too slow". In my measurements, 1,000 rectangles took 3.5 seconds and 5,000 took 21 seconds. For a tool that runs inside a quoting system or a production pipeline, that is the difference between an instant answer and a progress bar.

## Finding what was slow

Before changing anything, I measured. A profiler showed that about 90% of the time went into a single housekeeping step.

The algorithm keeps a list of the free spaces left in a bin. Each time it places a rectangle, some free spaces are cut into smaller ones, and any free space that sits entirely inside another is thrown away as redundant. The library did that clean-up by comparing every free space with every other one, after every placement. Placing 1,000 rectangles triggered 30.8 million of those comparisons.

Almost all of them were wasted. The list had already been cleaned after the previous placement, so the only spaces that could be redundant were the handful just created.

## The approach

I worked in two stages and measured each one separately.

**Stage 1: fix the algorithm, still in Python.** Checking only the newly created spaces, and removing a calculation the code performed twice, made the library 1.7x to 7.5x faster with no C++ at all. This matters for an honest account: a meaningful part of the gain is a smarter method, available to anyone, with nothing to compile.

**Stage 2: rewrite the hot path in C++.** I then re-implemented the four related packing methods in C++ and connected them to Python so that existing code keeps working. A user changes one line, the import, and nothing else. That stage supplies the rest of the speedup.

## The result

| Job | Before | After | Speedup |
|---|---|---|---|
| 1,000 rectangles, random sizes | 3.53 s | 0.014 s | 246x |
| 5,000 rectangles, random sizes | 21.1 s | 0.14 s | 155x |
| 2,000 game sprites | 1.50 s | 0.018 s | 85x |
| 2,000 sheet-cutting parts across 100 sheets | 0.42 s | 0.078 s | 5x |

## What could not be sped up

The last row is the honest counter-example. When a job spreads across many bins, most of the time is spent in a different part of the library, which asks each open bin in turn how well the next piece would fit. I left that part in Python, so those jobs gain about 5x, not 100x. Moving it to C++ is possible and would be the next step for a client with that kind of workload.

Two other limits:

- The fast path handles whole-number sizes. Fractional sizes still work but run at the original speed.
- The library offers two other families of packing methods that I did not port.

The measurements also have a limit. They were taken on one laptop that periodically slows down, probably from heat, so the times in seconds can vary by about 2x. The speedup ratios agreed to about 10% between full runs.

## How I know the answers are right

A fast wrong answer is worthless, so most of the effort went here.

- **Same output, checked at every step.** The original library is the reference. After every single placement, automated tests compare the new code's decision and its entire internal list of free spaces against the original's. There are 474 tests, including two that generate hundreds of random cases automatically and one that covers all 200 combinations of settings.
- **Awkward inputs.** Fractions, zero and negative sizes, absurdly large numbers, text where a number should be. The new code returns the same result or the same error as the original in every case.
- **Memory-safety tools.** The C++ was run under two standard checkers that detect memory errors and undefined behaviour. Both were clean.
- **Testing the tests.** I deliberately broke the C++ in six ways to see whether the tests would notice. They caught five. The sixth turned out to change nothing in the output.
- **Quirks preserved.** I found three small defects in the original library while porting it. I documented them and reproduced them, because a client replacing a library needs identical behaviour first. Fixing them is a separate decision.

## Reproduce it

The repository contains the benchmark script, the raw timing files and the tests. One command re-runs the benchmark, and it fails loudly if any output differs from the original.
