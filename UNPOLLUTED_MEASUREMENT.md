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
