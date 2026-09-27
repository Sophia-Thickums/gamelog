#!/usr/bin/env python3
"""
gamelog — measure a real game, not a synthetic.

WHY THIS EXISTS, in the words of the correction that produced it

We published a driver-option comparison using `vkmark`, and a Mesa developer replied:

    "I'm not a radv developer, but I don't consider vkmark to be very representative
     of real workloads."

She was right, and the numbers say so: a mid-range card scores 5,000-10,000 FPS in
vkmark, and our "GPU-bound" run recorded 62,297. **A synthetic that trivial is not a
measurement of a driver.** The industry standard for anything that matters is a real
rendering workload, and the metric is frame times -- not a score.

This tool wraps that standard procedure:

  1. launch a real game under the MangoHud logging layer
  2. collect the frame-time log it writes
  3. report median / p95 / p99 and a stutter ratio, not a single average

The tail is the part a player feels. An option that improves the median while wrecking
p99 is a regression, and comparing averages alone hides exactly that.

USAGE
    # list what we can measure
    gamelog --list

    # wrap a real game (Steam appid)
    gamelog run --appid 4508340 --label nte-baseline

    # or wrap any command
    gamelog run --label my-workload -- your-game-command --args

    # analyse a log you already have
    gamelog analyse ~/.local/share/mangohud/*.csv

    gamelog --selftest

NOTE ON STEAM: Steam must already be running, and this launches the app through it.
That is deliberate -- it is how you actually measure a game, and it means a human
starts Steam, not this script.

Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import glob
import io
import os
import statistics
import subprocess
import sys
import time

MANGO_DIR = os.path.expanduser("~/.local/share/mangohud")
FRAMETIME_COLS = ["frametime", "frame_time", "ft", "ms"]
FPS_COLS = ["fps"]


# ------------------------------------------------------------------ analysis

def find_col(header: list[str]):
    low = [h.strip().lower() for h in header]
    for c in FRAMETIME_COLS:
        if c in low:
            return header[low.index(c)], "ms"
    for c in FPS_COLS:
        if c in low:
            return header[low.index(c)], "fps"
    return None, ""


def load(path: str):
    rows = [r for r in csv.reader(io.StringIO(open(path, encoding="utf-8", errors="replace").read()))
            if any(c.strip() for c in r)]
    if not rows:
        return [], None, ""
    col, kind = find_col(rows[0])
    if not col:
        return [], None, ""
    try:
        idx = [h.strip().lower() for h in rows[0]].index(col.strip().lower())
    except ValueError:
        return [], None, ""
    vals = []
    for r in rows[1:]:
        if len(r) <= idx:
            continue
        try:
            v = float(r[idx])
        except ValueError:
            continue
        if v > 0:
            vals.append(1000.0 / v if kind == "fps" else v)
    return vals, col, kind


def pct(sv: list[float], p: float) -> float:
    if not sv:
        return float("nan")
    k = (len(sv) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(sv) - 1)
    return sv[lo] + (sv[hi] - sv[lo]) * (k - lo)


def report(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    s = sorted(vals)
    med = statistics.median(s)
    return {
        "n": len(s),
        "median_ms": round(med, 3),
        "mean_ms": round(statistics.fmean(s), 3),
        "p95_ms": round(pct(s, 95), 3),
        "p99_ms": round(pct(s, 99), 3),
        "max_ms": round(s[-1], 3),
        "stutter_ratio": round(pct(s, 99) / med, 3) if med else float("nan"),
        "effective_fps": round(1000.0 / med, 1) if med else float("nan"),
    }


# ------------------------------------------------------------------ the game wrapper

def list_games():
    """Steam games we can measure, from the local appmanifests."""
    out = []
    for f in glob.glob(os.path.expanduser("~/.local/share/Steam/steamapps/appmanifest_*.acf")):
        appid = os.path.basename(f).replace("appmanifest_", "").replace(".acf", "")
        try:
            txt = open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        import re
        m = re.search(r'"name"\s+"([^"]+)"', txt)
        size = re.search(r'"SizeOnDisk"\s+"(\d+)"', txt)
        name = m.group(1) if m else "?"
        # runtimes and tools are not games; listing them as "measurable" is noise
        if any(k in name for k in ("Proton", "Steam Linux Runtime", "Steam Controller")):
            continue
        out.append({
            "appid": appid,
            "name": name,
            "size_gb": round(int(size.group(1)) / 1e9, 1) if size else None,
        })
    return out


def run_wrapped(label: str, cmd: list[str] | None, appid: str | None, duration: int) -> int:
    os.makedirs(MANGO_DIR, exist_ok=True)
    before = set(glob.glob(os.path.join(MANGO_DIR, "*.csv")))
    env = dict(os.environ)
    env["MANGOHUD"] = "1"
    env["MANGOHUD_CONFIG"] = f"output_folder={MANGO_DIR},no_display,log_duration={duration}"

    if appid:
        cmd = ["steam", f"steam://rungameid/{appid}"]
    if not cmd:
        print("error: give --appid or a command after --", file=sys.stderr)
        return 2

    print(f"launching under MangoHud (logging for {duration}s): {' '.join(cmd)}")
    print("  -> play or leave it running; the log is written when the duration elapses.")
    try:
        subprocess.Popen(cmd, env=env)
    except OSError as e:
        print(f"  launch FAILED: {e}", file=sys.stderr)
        return 1

    print(f"waiting {duration}s ...")
    time.sleep(duration + 5)

    after = set(glob.glob(os.path.join(MANGO_DIR, "*.csv")))
    new = sorted(after - before)
    if not new:
        print("\nNO NEW LOG appeared. That is a real result, not an error:")
        print("  * MangoHud writes a log only when it attached to a running renderer")
        print("  * a launcher that hands off to another process can lose the layer")
        print("  * check that the game actually started, then re-run")
        return 1

    for path in new:
        vals, col, kind = load(path)
        r = report(vals)
        if not r.get("n"):
            print(f"{path}: no usable frame-time column")
            continue
        print(f"\n=== {label} ===")
        print(f"  log: {path}   column={col} ({kind})   frames={r['n']}")
        print(f"  median {r['median_ms']} ms (~{r['effective_fps']} fps)   mean {r['mean_ms']} ms")
        print(f"  p95 {r['p95_ms']} ms    p99 {r['p99_ms']} ms    max {r['max_ms']} ms")
        print(f"  stutter ratio (p99/median) {r['stutter_ratio']}"
              + ("   <-- spiky" if r["stutter_ratio"] and r["stutter_ratio"] > 1.5 else ""))
        print("\n  Record the TAIL. A higher average with a worse p99 is a regression.")
    return 0


# ------------------------------------------------------------------ selftest

def selftest() -> int:
    print("gamelog --selftest")
    print("=" * 60)
    ok = True

    vals = [16.0] * 95 + [33.0] * 4 + [100.0]
    r = report(vals)
    ok &= abs(r["median_ms"] - 16.0) < 0.01
    print(f"  {'PASS' if abs(r['median_ms']-16.0)<0.01 else 'FAIL'}  median on known set -> {r['median_ms']} ms")
    ok &= r["p99_ms"] > 30
    print(f"  {'PASS' if r['p99_ms']>30 else 'FAIL'}  p99 sees the tail -> {r['p99_ms']} ms")
    ok &= r["stutter_ratio"] > 1.5
    print(f"  {'PASS' if r['stutter_ratio']>1.5 else 'FAIL'}  flags a spiky run -> {r['stutter_ratio']}")

    smooth = report([16.0] * 100)
    ok &= abs(smooth["stutter_ratio"] - 1.0) < 0.01
    print(f"  {'PASS' if abs(smooth['stutter_ratio']-1.0)<0.01 else 'FAIL'}  "
          f"smooth run NOT flagged -> {smooth['stutter_ratio']} (negative control)")

    games = list_games()
    print(f"  --    real games discoverable -> {len(games)} "
          f"({', '.join(g['name'][:18] for g in games[:3])}...)")

    print("=" * 60)
    print("selftest " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gamelog",
                                 description="Measure a real game, not a synthetic.")
    sub = ap.add_subparsers(dest="which")

    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--list", action="store_true")

    r = sub.add_parser("run")
    r.add_argument("--label", required=True)
    r.add_argument("--appid")
    r.add_argument("--duration", type=int, default=60)
    r.add_argument("cmd", nargs=argparse.REMAINDER)

    a = sub.add_parser("analyse")
    a.add_argument("files", nargs="+")

    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.list or not args.which:
        games = list_games()
        print(f"{len(games)} measurable games:")
        for g in sorted(games, key=lambda x: x["name"]):
            print(f"  {g['appid']:>9}  {g['name'][:44]:<46} {g['size_gb']} GB")
        print("\n  gamelog run --appid <id> --label <name> --duration 60")
        return 0

    if args.which == "run":
        cmd = [c for c in (args.cmd or []) if c != "--"]
        return run_wrapped(args.label, cmd or None, args.appid, args.duration)

    if args.which == "analyse":
        rc = 0
        for pat in args.files:
            for path in (glob.glob(pat) or [pat]):
                vals, col, kind = load(path)
                rep = report(vals)
                if not rep.get("n"):
                    print(f"{path}: no usable frame-time column"); rc = 1; continue
                print(f"{path}  [{col}/{kind}]  frames={rep['n']}")
                print(f"  median {rep['median_ms']} ms (~{rep['effective_fps']} fps)"
                      f"   p95 {rep['p95_ms']}   p99 {rep['p99_ms']}"
                      f"   stutter {rep['stutter_ratio']}")
        return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
