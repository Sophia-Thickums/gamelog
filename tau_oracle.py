#!/usr/bin/env python3
"""
tau_oracle.py — TIME TO CONTACT: am I gaining on the thing in front of me?

Built 2026-09-30 from Kimi's recipe, which correctly rejected BOTH masks I
proposed and explained why each was a trap:

  "Low/high-flow separation is actively dangerous here. When you push into a
   wall, the wall's flow is near zero — flow-based masking would exclude exactly
   the surface you most need to measure. You'd mask out the patient."
  "The ring that excludes the center throws away your best signal."

Her actual recipe, which needs NO mask at all:

  1. DOROTATE FIRST. Fit the rotational component and subtract it. Rotation
     contaminates tau worse than any mask choice, and I already own the
     instrument that removes it (the flow-field classifier).
  2. ESTIMATE THE FOCUS OF EXPANSION (FOE) from the flow itself. A fixed
     central rectangle is only correct when walking dead ahead with zero yaw;
     the moment there is any look component the FOE migrates, and a fixed
     region then measures divergence "around the wrong point — a quiet version
     of today's bug: a confident number about a region that isn't the one the
     math assumes."
  3. PER-FEATURE tau, MEDIAN AGGREGATED. For pure forward translation each
     feature obeys |u_i| ~ r_i / tau, so tau_i = r_i / |u_i| is an independent
     estimate per feature. The median is SELF-MASKING: features on the body, on
     NPCs, on the sky, and codec-mush features are simply outliers, and a
     median does not care about outliers. "No rectangle to get wrong, because
     there is no rectangle."

tau is in FRAMES: "how many more frames until I am touching it." Falling tau =
gaining. tau large / unestimable = not approaching.

THE UNCERTAINTY CONTRACT (house rule, adopted from her): every reading returns
(value, uncertainty, n). Uncertainty here is the relative spread of the
per-feature estimates (MAD / median) — and per her, WIDENING SCATTER IS THE
EARLY WARNING that the encode is eating texture, which precedes any bias in the
median. That makes scatter a diagnostic, not just an error bar.
"""
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

ROWS, COLS = 180, 320
MAX_CORNERS, QUALITY, MIN_DIST = 140, 0.01, 8
MIN_FEATURES = 14
MIN_FLOW = 0.0006          # normalised px/frame; below this, no usable motion
DEROT_MIN = 0.0004


def _gray(a):
    if a is None:
        return None
    if a.dtype != np.uint8:
        a = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    if a.shape[1] != COLS or a.shape[0] != ROWS:
        a = cv2.resize(a, (COLS, ROWS))
    return cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)


def _flow(g1, g2):
    p0 = cv2.goodFeaturesToTrack(g1, MAX_CORNERS, QUALITY, MIN_DIST)
    if p0 is None or len(p0) < MIN_FEATURES:
        return None
    p1, st, _ = cv2.calcOpticalFlowPyrLK(
        g1, g2, p0, None, winSize=(15, 15), maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
    ok = st.reshape(-1) == 1
    if ok.sum() < MIN_FEATURES:
        return None
    a0 = p0.reshape(-1, 2)[ok].astype(np.float64)
    a1 = p1.reshape(-1, 2)[ok].astype(np.float64)
    h, w = g1.shape
    return a0, a1, np.array([w, h], dtype=np.float64), w, h


def derotate(a0, u, w, h):
    """Remove the best-fit ROTATIONAL field about the optical centre.

    Returns (residual_flow, omega). Kimi: rotation contaminates tau worse than
    any mask choice, and the rotation template is already the instrument that
    removes it.
    """
    c = np.array([w / 2.0, h / 2.0])
    r = a0 - c
    rn = np.linalg.norm(r, axis=1) + 1e-9
    # tangential unit vector (perpendicular to radius), y-down screen coords
    t = np.stack([-r[:, 1] / rn, r[:, 0] / rn], axis=1)
    omega = float(np.median((u * t).sum(axis=1) / rn))
    if abs(omega) < 1e-12:
        return u, 0.0
    rot = np.stack([-omega * r[:, 1], omega * r[:, 0]], axis=1)
    return u - rot, omega


def foe(a0, u):
    """Focus of expansion: the point the flow vectors radiate from.

    Each feature gives a LINE through a0 along its flow direction; the FOE is
    the point closest to all of them, solved in closed form (least squares).
    Unnormalised screen coordinates in, normalised fraction out.
    """
    dirs = u / (np.linalg.norm(u, axis=1, keepdims=True) + 1e-12)
    # minimise sum |(p - a) x d|^2  ->  A p = b
    A = np.zeros((2, 2))
    b = np.zeros(2)
    for a, d in zip(a0, dirs):
        n = np.array([-d[1], d[0]])
        A += np.outer(n, n)
        b += np.outer(n, n) @ a
    try:
        p = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return None
    return p


def time_to_contact(a, b):
    """tau in FRAMES. Returns the uncertainty contract dict."""
    if cv2 is None:
        return {"verdict": "no-cv2", "value": None, "uncertainty": 1.0, "n": 0}
    g1, g2 = _gray(a), _gray(b)
    if g1 is None or g2 is None:
        return {"verdict": "no-frame", "value": None, "uncertainty": 1.0, "n": 0}
    f = _flow(g1, g2)
    if f is None:
        return {"verdict": "unreadable", "value": None, "uncertainty": 1.0, "n": 0}
    a0, a1, scale, w, h = f
    u = (a1 - a0) / scale                       # normalised
    mag = np.linalg.norm(u, axis=1)
    usable = mag > MIN_FLOW
    if usable.sum() < MIN_FEATURES:
        return {"verdict": "no-approach", "value": None, "uncertainty": 0.2,
                "n": int(usable.sum()), "why": "flow below floor"}
    a0u, uu = a0[usable], u[usable]

    # 1. derotate
    res, omega = derotate(a0u, uu, w, h)
    rmag = np.linalg.norm(res, axis=1)
    keep = rmag > MIN_FLOW
    if keep.sum() < MIN_FEATURES:
        return {"verdict": "no-approach", "value": None, "uncertainty": 0.25,
                "n": int(keep.sum()), "omega": round(omega, 5),
                "why": "all flow was rotation"}

    # 2. FOE from the derotated flow
    p = foe(a0u[keep], res[keep])
    if p is None:
        return {"verdict": "no-foe", "value": None, "uncertainty": 1.0, "n": int(keep.sum())}

    # 3. per-feature tau_i = r_i / |u_i|, median aggregated (self-masking)
    r_norm = np.linalg.norm(a0u[keep] - p, axis=1) / np.array([w, h]).mean()
    tau_i = r_norm / rmag[keep]
    tau_i = tau_i[np.isfinite(tau_i)]
    if tau_i.size < 8:
        return {"verdict": "no-approach", "value": None, "uncertainty": 0.5, "n": int(tau_i.size)}
    med = float(np.median(tau_i))
    mad = float(np.median(np.abs(tau_i - med)))
    unc = float(np.clip(1.5 * mad / (abs(med) + 1e-9), 0.0, 1.0))
    # ★ TEXTURE POVERTY IS ITS OWN UNCERTAINTY TERM (Kimi, 09-30). Synthetics
    # are texture-rich so tau is exact; real game walls are often painted flat
    # and LK finds almost nothing to track. Falling n is NOT "the wall is far" —
    # it is "the wall is boring", and the median of a handful of features is a
    # confident number about nothing. So n votes: a shrinking survivor count
    # raises uncertainty on its own, independent of the scatter.
    n_pen = float(np.clip((MIN_FEATURES * 2 - tau_i.size) / (MIN_FEATURES * 2), 0.0, 0.5))
    unc = float(np.clip(unc + n_pen, 0.0, 1.0))
    # ★ THE CONTRACT HAS TO BIND THE VERDICT, NOT JUST DECORATE IT (self-test,
    # 09-30): a pure horizontal TRANSLATION (a pan) produced tau=14.9 and this
    # function called it 'approaching' while reporting uncertainty 0.70. The
    # scatter was correct and the verdict ignored it — the uncertainty number
    # was the tell and it did not vote. A degenerate FOE fit (translation with
    # no expansion) gives a meaningless but finite tau, so the gate is now:
    # approaching requires LOW uncertainty. High scatter => 'unclear', never a
    # confident number about something the math does not actually hold for.
    if unc >= 0.45:
        verdict = "unclear"
    elif med < 60:
        verdict = "approaching"
    else:
        verdict = "no-approach"
    nfoe = (p / scale) if p is not None else None
    return {"verdict": verdict,
            "value": round(med, 3), "uncertainty": round(unc, 3),
            "n": int(tau_i.size), "n_penalty": round(n_pen, 3),
            "omega": round(omega, 5),
            "foe": None if nfoe is None else [round(float(nfoe[0] / w), 3),
                                              round(float(nfoe[1] / h), 3)],
            "scatter": round(mad, 3)}


def _self_test():
    """KNOWN-ANSWER test. A pure SCALE about a point has a uniform, exactly
    known tau: scaling by s moves a point at radius r outward by (s-1)r, so
    tau = r / ((s-1) r) = 1/(s-1) — the same for every feature, which is
    precisely why this makes a clean oracle."""
    if cv2 is None:
        print("cv2 missing")
        return False
    h, w = ROWS, COLS
    yy, xx = np.mgrid[0:h, 0:w]
    base = (0.5 + 0.25 * np.sin(xx / 9.0) * np.sin(yy / 7.0)
            + 0.2 * np.sin((xx * 0.7 + yy * 1.3) / 13.0))
    img = np.stack([base, base * .95, base * .9], axis=-1).astype(np.float32)
    ok = True

    def scale_img(s):
        M = np.float32([[s, 0, -s * w / 2 + w / 2], [0, s, -s * h / 2 + h / 2]])
        return cv2.warpAffine(img, M, (w, h))

    def shift_img(dx):
        return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, 0]]), (w, h))

    cases = [("scale 1.05 (tau=20)", scale_img(1.05), 20.0),
             ("scale 1.10 (tau=10)", scale_img(1.10), 10.0),
             ("scale 1.02 (tau=50)", scale_img(1.02), 50.0)]
    for name, b, want in cases:
        r = time_to_contact(img, b)
        got = r.get("value")
        good = got is not None and abs(got - want) / want < 0.35
        if not good:
            ok = False
        print(f"  [{'ok ' if good else 'BAD'}] {name:<22} got tau={got} "
              f"(want ~{want}) unc={r.get('uncertainty')} n={r.get('n')} foe={r.get('foe')}")

    # negative controls: pure translation = no approach, and static
    for name, b in (("pure shift (yaw)", shift_img(12)), ("static", img.copy())):
        r = time_to_contact(img, b)
        good = r.get("verdict") in ("no-approach", "unclear")
        if not good:
            ok = False
        print(f"  [{'ok ' if good else 'BAD'}] {name:<22} verdict={r.get('verdict')} "
              f"tau={r.get('value')} unc={r.get('uncertainty')} omega={r.get('omega')}")
    print(f"  self-test: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    args = sys.argv[1:]
    if "--live" in args:
        # live mode: drive whatever capture callable the host provides.
        # Deliberately NOT bundled — this module carries no game-specific code.
        print("live mode: import time_to_contact() and feed it consecutive frames.")
        print("see README: the oracle must pass --self-test first.")
    else:
        print("=== KNOWN-ANSWER SELF-TEST (synthetic scaling = exact tau) ===")
        ok = _self_test()
        print()
        print("PASS — this instrument may report on real workloads." if ok else
              "FAIL — this instrument does NOT get to report on real workloads.")
