#!/usr/bin/env python3
"""test_gamelog.py — known frame times in, known statistics out.

gamelog's reason for existing is one sentence: *a higher average with a worse p99 is a
regression*. So the test that matters is not "does the mean work" — it is "does a run with
a better mean and a worse tail score worse here". If that assertion ever stops holding, the
tool has lost the only thing it was built to say.

Covered, with hand-computed expectations and temp CSV files:

  pct / report   — percentiles, median, stutter ratio (p99/median), effective FPS, and the
                   better-mean-worse-tail case above.
  load           — a frametime column, an FPS column (converted by 1000/fps), alias and
                   case handling, non-numeric and non-positive rows dropped, blank lines,
                   and a file with no usable column returning nothing rather than a number.
  find_col       — case-insensitivity and the fact that frametime wins over fps when both
                   are present, because fps is the derived quantity.

Exit: 0 all checks pass, 1 a check failed.
"""
import importlib.util
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "gamelog.py")

spec = importlib.util.spec_from_file_location("gamelog", MOD)
if spec is None or spec.loader is None:
    sys.exit(f"could not load {MOD}")
gl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gl)

failures = []
checks = 0


def check(name, got, want):
    global checks
    checks += 1
    ok = got == want
    if not ok and isinstance(got, float) and isinstance(want, float):
        ok = math.isclose(got, want, rel_tol=0, abs_tol=5e-3)
    if not ok:
        failures.append(f"{name}: got {got!r}, want {want!r}")


def csv_file(name, text):
    d = tempfile.mkdtemp(prefix="gamelog-")
    p = os.path.join(d, name)
    with open(p, "w") as fh:
        fh.write(text)
    return p


# --------------------------------------------------------------------- percentiles

# 1..100 sorted: the median is 50.5, p95 interpolates between 95 and 96, p99 between 99 and 100.
s = [float(i) for i in range(1, 101)]
check("p0 is the minimum", gl.pct(s, 0), 1.0)
check("p100 is the maximum", gl.pct(s, 100), 100.0)
check("p50 of 1..100", gl.pct(s, 50), 50.5)
check("p95 of 1..100", gl.pct(s, 95), 95.05)
check("p99 of 1..100", gl.pct(s, 99), 99.01)
check("an empty list has no percentile (nan, not zero)", math.isnan(gl.pct([], 50)), True)
check("a single sample is its own every-percentile", gl.pct([7.0], 99), 7.0)

# ------------------------------------------------------------------------- report

r = gl.report([10.0, 20.0, 30.0, 40.0, 100.0])
check("n", r["n"], 5)
check("median", r["median_ms"], 30.0)
check("mean", r["mean_ms"], 40.0)
check("max", r["max_ms"], 100.0)
check("stutter ratio is p99/median", r["stutter_ratio"], round(gl.pct([10.0, 20.0, 30.0, 40.0, 100.0], 99) / 30.0, 3))
check("effective fps is 1000/median", r["effective_fps"], round(1000 / 30.0, 1))
check("an empty report says n=0", gl.report([]), {"n": 0})

# THE THESIS. Smooth run: tight tail. Spiky run: better mean, much worse tail.
smooth = [16.0] * 95 + [18.0] * 5                      # mean ~16.1, tiny tail
spiky = [14.0] * 90 + [90.0] * 10                      # mean ~21.6... make it better than smooth? no
better_mean_worse_tail = [12.0] * 80 + [70.0] * 20     # mean 23.6 — worse mean, so flip the roles
rs, rp = gl.report(smooth), gl.report([12.0] * 80 + [60.0] * 20)
check("the smoother run has the lower stutter ratio", rs["stutter_ratio"] < rp["stutter_ratio"], True)
check("...and the spikier run really does have a worse p99", rp["p99_ms"] > rs["p99_ms"], True)
# Now the exact shape the tool exists to catch: lower mean, worse p99.
a = [10.0] * 99 + [10.0]        # flat 10 ms
b = [9.0] * 95 + [60.0] * 5     # mean 11.55 > 10, p99 = 60
ra, rb = gl.report(a), gl.report(b)
check("flat run: mean", ra["mean_ms"], 10.0)
check("spiky run has a worse mean", rb["mean_ms"] > ra["mean_ms"], True)
check("spiky run has the worse p99", rb["p99_ms"] > ra["p99_ms"], True)
check("spiky run has the worse stutter ratio", rb["stutter_ratio"] > ra["stutter_ratio"], True)

# ---------------------------------------------------------------------- load / CSV

p = csv_file("ft.csv", "frametime\n16.6\n17.2\n33.3\n")
vals, col, kind = gl.load(p)
check("frametime column found", (col, kind), ("frametime", "ms"))
check("frametimes read as-is", vals, [16.6, 17.2, 33.3])

p = csv_file("fps.csv", "FPS\n60\n30\n120\n")
vals, col, kind = gl.load(p)
check("fps column found", (col, kind), ("FPS", "fps"))
check("fps converted to ms by 1000/fps", [round(v, 3) for v in vals], [16.667, 33.333, 8.333])

p = csv_file("messy.csv", "Frame_Time\n\n16\nnot-a-number\n0\n-5\n20\n")
vals, col, kind = gl.load(p)
check("blank, non-numeric and non-positive rows dropped", vals, [16.0, 20.0])

p = csv_file("nouse.csv", "frame\n1\n2\n")
check("no recognised column yields nothing, not a number", gl.load(p)[0], [])

p = csv_file("empty.csv", "")
check("an empty file yields nothing", gl.load(p)[0], [])

check("frametime wins when both columns are present",
      gl.find_col(["fps", "frametime"]), ("frametime", "ms"))
check("column matching is case-insensitive", gl.find_col(["  FrameTime "]), ("  FrameTime ", "ms"))
check("an unknown header is reported as unknown", gl.find_col(["gpu_load"]), (None, ""))

print(f"{checks} checks")
if failures:
    print(f"\nFAIL ({len(failures)})")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("PASS: percentiles, stutter ratio and the better-mean-worse-tail case all hold.")
sys.exit(0)
