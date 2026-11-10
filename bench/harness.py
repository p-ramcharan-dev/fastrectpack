"""Benchmark harness: warm-up, repetitions, median and spread, output digest, environment capture.

The same functions are used for the original and the accelerated code, so both are measured identically.
"""
import gc
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time


def digest(rect_list):
    """Stable fingerprint of a full packing result (bin, x, y, w, h, rid for every rectangle, in order)."""
    return hashlib.sha256(repr(rect_list).encode()).hexdigest()[:16]


def run_pack(mod, rects, bins, **packer_kwargs):
    """Build a packer from module `mod` (rectpack or the accelerated package), pack, return rect_list()."""
    p = mod.newPacker(**packer_kwargs)
    for w, h, rid in rects:
        p.add_rect(w, h, rid)
    for w, h, count in bins:
        p.add_bin(w, h, count)
    p.pack()
    return p.rect_list()


def pin(cpu):
    """Pin this process to one logical CPU and raise its priority (Windows).

    Why: on this machine (hybrid Intel CPU) the same loop runs 1.5x to 4x slower on some logical CPUs, and an
    unpinned process drifts between them, giving run-to-run swings of up to 4x. See bench/probe_cores.py.
    """
    if sys.platform != "win32" or cpu is None:
        return {"pinned_cpu": None}
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    proc = k32.GetCurrentProcess()
    cpus = list(cpu) if isinstance(cpu, (list, tuple, range)) else [cpu]
    mask = 0
    for c in cpus:
        mask |= 1 << c
    ok = bool(k32.SetProcessAffinityMask(proc, mask))
    prio = bool(k32.SetPriorityClass(proc, 0x80))  # HIGH_PRIORITY_CLASS
    return {"pinned_cpus": cpus if ok else None, "high_priority": prio}


def measure(fn, reps, warmup):
    """Run fn() warmup+reps times. Returns timing stats (seconds) and the result of the last run.

    Wall time is the headline; CPU time (process_time) is recorded too, so a run that was slowed by
    contention (wall >> cpu) can be told apart from one that simply did more work.
    """
    result = None
    for _ in range(warmup):
        result = fn()
    times, cpu_times = [], []
    for _ in range(reps):
        gc.collect()
        c0 = time.process_time()
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
        cpu_times.append(time.process_time() - c0)
    s = sorted(times)
    q = statistics.quantiles(s, n=4) if len(s) >= 4 else None
    return {
        "reps": reps, "warmup": warmup,
        "median_s": statistics.median(s), "min_s": s[0], "max_s": s[-1],
        "mean_s": statistics.fmean(s), "stdev_s": statistics.stdev(s) if len(s) > 1 else 0.0,
        "iqr_s": (q[2] - q[0]) if q else None,
        "all_s": times, "cpu_s": cpu_times,
    }, result


def compare(fns, reps, warmup=1):
    """Interleaved A/B(/C...) timing. fns: {name: callable}. Each round runs every variant once, in rotating
    order, so background load on a shared machine hits all variants alike. Returns per-variant stats, the
    per-round speedup of each variant against the first one, and each variant's last result.

    Speedup is computed per round (first_time / variant_time) and then summarised, which is more robust to a
    noisy machine than dividing two separately-measured medians.
    """
    names = list(fns)
    results = {}
    for _ in range(warmup):
        for n in names:
            results[n] = fns[n]()
    times = {n: [] for n in names}
    for r in range(reps):
        order = names[r % len(names):] + names[:r % len(names)]
        for n in order:
            gc.collect()
            t0 = time.perf_counter()
            results[n] = fns[n]()
            times[n].append(time.perf_counter() - t0)
    base = names[0]
    out = {}
    for n in names:
        s = sorted(times[n])
        ratios = [times[base][i] / times[n][i] for i in range(reps)]
        out[n] = {
            "median_s": statistics.median(s), "min_s": s[0], "max_s": s[-1],
            "stdev_s": statistics.stdev(s) if reps > 1 else 0.0, "all_s": times[n],
            # HEADLINE: ratio of best (minimum) times. Background load only ever ADDS time, and it hits long runs
            # (the slow original) harder than short ones, so medians of ratios flatter the faster code.
            "speedup_vs_" + base + "_best_of": min(times[base]) / min(times[n]),
            "speedup_vs_" + base + "_median": statistics.median(ratios),
            "speedup_vs_" + base + "_min": min(ratios), "speedup_vs_" + base + "_max": max(ratios),
        }
    return out, results


def environment():
    def sh(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True).stdout.strip()
        except Exception:  # noqa: BLE001
            return ""
    env = {
        "python": sys.version.replace("\n", " "),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    if sys.platform == "win32":
        env["cpu"] = sh('powershell -NoProfile -Command "(Get-CimInstance Win32_Processor).Name"')
        env["power_plan"] = sh('powershell -NoProfile -Command "powercfg /getactivescheme"')
        env["ram_gb"] = sh('powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)"')
    for name in ("rectpack", "fastrectpack"):
        try:
            from importlib.metadata import version
            env[f"{name}_version"] = version(name)
        except Exception:  # noqa: BLE001
            pass
    return env


def dump(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
