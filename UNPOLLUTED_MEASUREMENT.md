# Unpolluted-measurement setup (2026-09-26)

## The confound
Ollama's service is pinned `MESA_VK_DEVICE_SELECT=1002:7550!` — EXCLUSIVE to the 9070 XT.
So every vision-model load lands on the SAME card a game renders on. A frame-time
measurement taken with that in place measures the game *plus* my model, and calls it the game.

## The fix (Ryan's idea, and better than a service restart)
A SECOND ollama instance pinned to the VEGA FE, on its own port. The main one is untouched.

    MESA_VK_DEVICE_SELECT=1002:6863! OLLAMA_HOST=127.0.0.1:11435 \
      OLLAMA_MODELS=/var/lib/ollama/.ollama/models ollama serve

Measured: VL model loaded at 5.27 GB VRAM on card0 (Vega FE).
card1 (9070 XT) stayed at 0.49 GB — clear for a game.
Cost: 11.1 s cold load+run on the Vega. Slower than the XT, and it does not matter:
this instance is for glances DURING a measurement, not for speed.

## The law it produces
A MEASUREMENT MUST NOT SHARE THE RESOURCE IT MEASURES.
Reading a frame time while my own model occupies the same GPU is not a reading of the
game — it is a reading of the game plus me. Route the observer OFF the observed.


## Second instrument trap, measured 2026-09-27 (Control, maxed)
MangoHud 0.8.4 on this RDNA4 card records **fps and frametime correctly** and
**every GPU hardware column wrong**:

| column | reading | truth at the same moment |
|---|---|---|
| `fps` / `frametime` | exact to 5 dp, cluster on the 164.83 Hz cap | correct |
| `gpu_load` | 0.0% | **100.0%** (sysfs `gpu_busy_percent`) |
| `gpu_core_clock` | constant 600 | 2813 MHz (`pp_dpm_sclk`) |
| `gpu_vram_used` | constant 0.0156 | 15.0 GB (`mem_info_vram_used`) |

**Rule: never quote a MangoHud hardware column on an unverified card.** Cross-check
against sysfs, or do not publish it. The fps column earned trust by agreeing with its
own frametime column and by landing on a known panel cap; the others never had a check.

## The bimodal-median trap, same session
A run that alternates between a frame cap and a stall has TWO populations, and the
median reports whichever is numerically larger in COUNT, not in TIME:

    frame-weighted median  164.8 fps      <- a benchmark would print this
    time actually spent    ~10 fps for 67% of the run

The player experienced the second. **Report the distribution and the time spent in each
regime, never one central number over a bimodal run.** Both facts came from one file;
only one of them was the truth about the experience.
