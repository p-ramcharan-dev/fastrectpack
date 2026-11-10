"""Time the same fixed CPU-bound loop pinned to each logical CPU, to tell fast (P) cores from slow (E) cores.
Windows only. Prints one line per logical CPU."""
import ctypes
import sys
import time

if sys.platform != "win32":
    raise SystemExit("Windows only")

k32 = ctypes.windll.kernel32
k32.GetCurrentProcess.restype = ctypes.c_void_p
k32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
proc = k32.GetCurrentProcess()


def work():
    t = time.perf_counter()
    x = 0
    for i in range(3_000_000):
        x += (i * 7) ^ (i >> 3)
    return time.perf_counter() - t


n = 28
rows = []
for cpu in range(n):
    if not k32.SetProcessAffinityMask(proc, 1 << cpu):
        print(cpu, "could not pin")
        continue
    time.sleep(0.05)
    best = min(work() for _ in range(3))
    rows.append((cpu, best))
    print(f"cpu {cpu:2d}: {best*1000:7.1f} ms", flush=True)

fast = min(t for _, t in rows)
print("\nfastest:", f"{fast*1000:.1f} ms;", "CPUs within 15% of fastest:", [c for c, t in rows if t <= fast * 1.15])
print("slower CPUs:", [(c, round(t / fast, 2)) for c, t in rows if t > fast * 1.15])
