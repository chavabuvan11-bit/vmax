#!/usr/bin/env python3
"""
compare.py - score a candidate cut against a reference style.

  python3 compare.py REFERENCE/analysis.json CANDIDATE/analysis.json [--md out.md]

Both inputs come from deconstruct.py. Prints a table of measurable style
traits (rhythm, exposure, colour, camera motion, music sync), a verdict per
row, and plain-language fixes for whatever is off. A match on numbers is
necessary, not sufficient: still look at both contact sheets side by side.
"""

import argparse
import json
import sys

MOTION_GROUPS = {
    "locked-off": "static", "black": None, "too short to read": None,
    "unreadable (flat/flashing)": None,
}


def motion_group(label):
    if label in MOTION_GROUPS:
        return MOTION_GROUPS[label]
    for key, grp in (("push-in", "push-in"), ("pull-out", "pull-out"), ("pan/truck", "lateral"),
                     ("tilt/pedestal", "vertical"), ("handheld", "handheld")):
        if key in label:
            return grp
    return None


def motion_profile(a):
    tot, prof = 0.0, {}
    for s in a["shots"]:
        groups = {motion_group(p) for p in s["motion"]["label"].split(", ")} - {None}
        for g in groups:
            prof[g] = prof.get(g, 0.0) + s["dur"]
        if groups:
            tot += s["dur"]
    return {k: v / tot for k, v in prof.items()} if tot else {}


def hex2rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def palette_distance(ref, cand):
    if not ref or not cand:
        return None
    cr = [hex2rgb(p["hex"]) for p in cand]
    d = 0.0
    for p in ref:
        r = hex2rgb(p["hex"])
        d += p["share"] * min(sum((x - y) ** 2 for x, y in zip(r, c)) ** 0.5 for c in cr)
    return d / sum(p["share"] for p in ref)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reference")
    ap.add_argument("candidate")
    ap.add_argument("--md", help="also write the table to this markdown file")
    args = ap.parse_args()
    with open(args.reference) as f:
        R = json.load(f)
    with open(args.candidate) as f:
        C = json.load(f)

    rows, fixes = [], []

    def ratio_row(name, r, c, tol, fix_hi, fix_lo, unit="", fmt="{:.2f}"):
        if r is None or c is None or r == 0:
            rows.append((name, fmt.format(r) if r is not None else "-", fmt.format(c) if c is not None else "-", "n/a"))
            return
        q = c / r
        ok = abs(q - 1) <= tol
        rows.append((name, fmt.format(r) + unit, fmt.format(c) + unit, "match" if ok else f"{q:.2f}x"))
        if not ok:
            fixes.append((fix_hi if q > 1 else fix_lo).format(r=fmt.format(r) + unit, c=fmt.format(c) + unit))

    def abs_row(name, r, c, tol, fix_hi, fix_lo, fmt="{:.3f}"):
        if r is None or c is None:
            rows.append((name, "-", "-", "n/a"))
            return
        d = c - r
        ok = abs(d) <= tol
        rows.append((name, fmt.format(r), fmt.format(c), "match" if ok else f"{d:+.3f}"))
        if not ok:
            fixes.append((fix_hi if d > 0 else fix_lo).format(r=fmt.format(r), c=fmt.format(c)))

    re_, ce = R["editing"], C["editing"]
    ratio_row("Average shot length", re_["asl_s"], ce["asl_s"], 0.25,
              "Shots run long ({c} vs {r}). Trim heads/tails or split coverage; cut on action.",
              "Cutting faster than the reference ({c} vs {r}). Hold shots longer and let moves finish.", "s")
    ratio_row("Median shot length", re_["median_shot_s"], ce["median_shot_s"], 0.25,
              "Typical shot is longer than the reference ({c} vs {r}).",
              "Typical shot is shorter than the reference ({c} vs {r}).", "s")
    ratio_row("Cuts per minute", re_["cuts_per_min"], ce["cuts_per_min"], 0.25,
              "Too many cuts ({c} vs {r}/min).", "Too few cuts ({c} vs {r}/min).", "", "{:.1f}")

    rc, cc = R["color"], C["color"]
    abs_row("Mean luma (key)", rc["luma"], cc["luma"], 0.05,
            "Brighter than reference ({c} vs {r}): lower exposure / key, or pull down mids in the grade.",
            "Darker than reference ({c} vs {r}): open up, add fill, or lift mids.")
    abs_row("Contrast (luma SD)", rc["contrast"], cc["contrast"], 0.03,
            "More contrast than reference: soften key-to-fill ratio or flatten the curve.",
            "Flatter than reference: harder key, less fill, steeper S-curve.")
    abs_row("Black point", rc["black_pt"], cc["black_pt"], 0.03,
            "Blacks lifted vs reference: sink the toe / remove the matte.",
            "Blacks crushed vs reference: lift the toe for a matte floor.")
    abs_row("White point", rc["white_pt"], cc["white_pt"], 0.05,
            "Highlights hotter than reference: roll off the shoulder.",
            "Highlights duller than reference: let speculars and practicals bloom higher.")
    abs_row("Saturation", rc["saturation"], cc["saturation"], 0.06,
            "Over-saturated vs reference: pull saturation / use a more muted palette in wardrobe & set.",
            "Under-saturated vs reference: push saturation or add colour in production design.")
    abs_row("Warmth (R-B)", rc["warmth"], cc["warmth"], 0.03,
            "Warmer than reference: cooler white balance or teal shift.",
            "Cooler than reference: warmer white balance, tungsten/practical light.")
    abs_row("Tint (G-RB)", rc["tint"], cc["tint"], 0.02,
            "Greener than reference: add magenta.", "More magenta than reference: add green.")
    pd = palette_distance(rc.get("palette"), cc.get("palette"))
    rows.append(("Palette distance", "0", f"{pd:.3f}" if pd is not None else "-",
                 "n/a" if pd is None else ("match" if pd <= 0.12 else "off")))
    if pd is not None and pd > 0.12:
        fixes.append("Palette drifts from the reference; compare the hex swatches in both reports "
                     "and steer set dressing, wardrobe and grade toward the reference colours.")
    ra, ca = R["frame"]["active_aspect"], C["frame"]["active_aspect"]
    abs_row("Active picture aspect", ra, ca, 0.03,
            "Frame is wider than reference ({c} vs {r}).", "Frame is narrower than reference ({c} vs {r}).", "{:.2f}")

    rm, cm = motion_profile(R), motion_profile(C)
    keys = sorted(set(rm) | set(cm))
    l1 = sum(abs(rm.get(k, 0) - cm.get(k, 0)) for k in keys) / 2
    for k in keys:
        rows.append((f"Motion: {k} (screen time)", f"{rm.get(k, 0) * 100:.0f}%", f"{cm.get(k, 0) * 100:.0f}%",
                     "" if abs(rm.get(k, 0) - cm.get(k, 0)) <= 0.15 else "off"))
    rows.append(("Motion mix difference", "0%", f"{l1 * 100:.0f}%", "match" if l1 <= 0.25 else "off"))
    if l1 > 0.25:
        worst = max(keys, key=lambda k: abs(rm.get(k, 0) - cm.get(k, 0)))
        more = cm.get(worst, 0) > rm.get(worst, 0)
        fixes.append(f"Camera grammar differs most on '{worst}': "
                     f"{'use less of it' if more else 'use more of it'} "
                     f"(reference {rm.get(worst, 0) * 100:.0f}% of screen time, yours {cm.get(worst, 0) * 100:.0f}%).")

    ra_, ca_ = R.get("audio") or {}, C.get("audio") or {}
    if ra_.get("cuts_on_onset") is not None and ca_.get("cuts_on_onset") is not None:
        abs_row("Cuts on audio onset", ra_["cuts_on_onset"], ca_["cuts_on_onset"], 0.15,
                "Cutting on the beat more than the reference does: let some cuts land off-beat.",
                "Reference cuts on the beat more than you do: snap cuts to onsets/downbeats.", "{:.2f}")
    if ra_.get("tempo_bpm") and ca_.get("tempo_bpm"):
        q = ca_["tempo_bpm"] / ra_["tempo_bpm"]
        near = min(abs(q - 1), abs(q - 2), abs(q - 0.5))
        rows.append(("Music tempo", f"{ra_['tempo_bpm']}", f"{ca_['tempo_bpm']}", "match" if near <= 0.06 else f"{q:.2f}x"))
        if near > 0.06:
            fixes.append(f"Music tempo differs ({ca_['tempo_bpm']} vs {ra_['tempo_bpm']} bpm): pick a track near the reference tempo.")

    matched = sum(1 for r in rows if r[3] == "match")
    scored = sum(1 for r in rows if r[3] not in ("", "n/a"))
    out = ["| Trait | Reference | Candidate | Verdict |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    out.append(f"\n**{matched}/{scored} measurable traits match.**\n")
    if fixes:
        out.append("### What to change")
        out += [f"- {f}" for f in fixes]
    else:
        out.append("Numbers line up. Now compare the contact sheets for framing, lensing and lighting direction.")
    text = "\n".join(out)
    print(text)
    if args.md:
        with open(args.md, "w") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
