# Security policy

## Reporting a vulnerability

Please report privately through GitHub: open the **Security** tab of this repository and choose **Report a vulnerability**. Do not open a public issue for security problems.

fastrectpack is a small project maintained by one person. I will acknowledge a report as soon as I can and will tell you what I plan to do, but I cannot promise a response time.

## What counts

The package contains a native (C++) extension, so the realistic risks are memory-safety problems: an out-of-bounds read or write, a crash, or undefined behaviour reachable from Python with unusual input (for example very large sizes, or objects that raise during conversion). The test suite is run under AddressSanitizer and UndefinedBehaviorSanitizer in CI, which lowers the risk but does not remove it.

## Supported versions

Only the latest release receives fixes.

## Not in scope

Behaviour that is inherited unchanged from `rectpack` (for example the packing algorithms themselves) should be reported to [secnot/rectpack](https://github.com/secnot/rectpack).
