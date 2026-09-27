# gamelog

**Measure a real game, not a synthetic.**

## Why this exists

We published a driver-option comparison using `vkmark`. A Mesa developer replied:

> *"I'm not a radv developer, but I don't consider vkmark to be very representative of real workloads."*

She was right, and our own numbers prove it. linuxreviews.org on vkmark: *"too simple for modern
hardware"* — a mid-range card scores 5,000–10,000 FPS in it. Our "GPU-bound" run recorded
**62,297**. A synthetic that trivial is not a measurement of a driver.

The industry standard for anything that matters is a **real rendering workload**, and the metric is
**frame times**, not a score. Specifically:

| what to report | why |
|---|---|
| median frame time | the typical experience |
| **p95 and p99 frame time** | **what a player actually feels** |
| stutter ratio (p99 / median) | how spiky it is, in one number |
| the full stack: game, Proton, DXVK/vkd3d, Mesa, kernel | a result without its stack is an anecdote |

**A higher average with a worse p99 is a regression.** Comparing averages alone hides exactly the
thing the measurement exists to catch.

## Install

```bash
git clone https://github.com/Sophia-Thickums/gamelog
cd gamelog
python3 gamelog.py --selftest        # proves the analyser can compute, and can stay quiet
python3 gamelog.py --list            # what you can measure
```

Requires `mangohud` (the frame-time capture layer — this is what the standard procedure uses).
Standard library otherwise.

## Use

```bash
# measure a real game for 60 seconds
python3 gamelog.py run --appid 4508340 --label nte-baseline --duration 60

# or wrap any command with a window
python3 gamelog.py run --label my-app -- my-rendering-app --args

# analyse logs you already have
python3 gamelog.py analyse ~/.local/share/mangohud/*.csv
```

**Steam must already be running.** This launches through Steam deliberately — it is how you
actually measure a game, and it means a human starts Steam, not a script.

## When there is no log, that is a result

MangoHud writes a log only when it attached to a running renderer. If a launcher hands off to
another process, the layer can be lost. `gamelog` says so plainly instead of reporting an empty
analysis — *a monitor that cannot see must never report absence.*

## Limits

- **One game is one game.** Performance is application-specific; that is the entire premise of
  per-app profiles. Measure the titles you actually play.
- **Frame times need a real renderer.** A synthetic that runs at 60,000 FPS cannot show you a
  difference no matter how many times you run it.
- **It does not control the game.** You play; it measures. There is no automation of gameplay here.
- **MangoHud crashed one synthetic benchmark in testing** (`vkmark`: `free(): invalid pointer`).
  That is a real incompatibility, recorded rather than worked around.
- **★ MangoHud's GPU columns are NOT reliable on every card — verify yours before quoting them.**
  Measured 2026-09-27 on an RX 9070 XT (RDNA4, Mesa 26.2.3) with MangoHud 0.8.4: the `fps` and
  `frametime` columns were exact (1000/fps matched `frametime` to five decimal places, and the
  fast cluster sat precisely on the panel's 164.83 Hz cap), but **every hardware column was dead** —
  `gpu_load` read `0.0%` *while the card was at 100% busy*, `gpu_core_clock` was pinned at a
  constant `600`, and `gpu_vram_used` returned the same 0.0156 on every row including the ones
  inside a hard hitch. Reading those columns would have produced a confident, publishable, entirely
  fictional bottleneck analysis. **Cross-check any GPU column against sysfs before believing it:**
  `/sys/class/drm/card*/device/gpu_busy_percent`, `.../mem_info_vram_used`, `.../pp_dpm_sclk`,
  `.../mem_info_gtt_used`. `gamelog` reports frame timing; it does not vouch for the hardware
  columns of the tool that captured them.
- **A median across a mixed run describes neither half.** The same session showed a frame-weighted
  median of **164.8 fps** and a *time*-weighted picture of the run sitting at **~10 fps for 67% of
  its duration**, because the two clusters were a 165 Hz cap and a stall. Always report the
  distribution and the time spent in each regime — a single central number over a bimodal run is
  not a summary, it is a coin flip.

## Background

Built the evening a Mesa driver developer told us our benchmark wasn't representative. The honest
response to that is not a better synthetic — it is a real workload and the statistics the industry
actually uses.

MIT licensed.
