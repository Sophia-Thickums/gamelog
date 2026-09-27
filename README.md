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

## Background

Built the evening a Mesa driver developer told us our benchmark wasn't representative. The honest
response to that is not a better synthetic — it is a real workload and the statistics the industry
actually uses.

MIT licensed.
