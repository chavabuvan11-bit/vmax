#!/usr/bin/env python3
"""
deconstruct.py - measure the craft of a reference video.

Turns a video (local file or any yt-dlp URL) into a folder of evidence that
Claude can read and look at:

  report.md          human-readable summary + per-shot table
  analysis.json      every number, machine-readable (used by compare.py)
  contact_*.jpg      grids of one keyframe per shot, labelled
  barcode.png        colour-over-time strip with cut marks
  frames/            keyframes per shot (start / mid / end for long shots)
  transcript.txt     captions with timestamps, if any were available
  source/            the downloaded video + metadata (URL sources only)

Usage:
  python3 deconstruct.py SOURCE [-o OUTDIR] [--sensitivity 3.0] [--hard 0.45]
                                [--min-shot 0.10] [--fps 12] [--max-height 720]
                                [--no-audio] [--no-subs] [--subs FILE.vtt]

Needs: ffmpeg + ffprobe on PATH, numpy, Pillow. yt-dlp only for URLs.
Everything measured here is a heuristic. Treat it as evidence to check
against the frames, not as ground truth.
"""

import argparse
import concurrent.futures as cf
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ANALYSIS_W = 192          # width of the low-res decode used for colour + motion
MAX_ANALYSIS_FRAMES = 6000
SHOT_LEN_BUCKETS = [0.5, 1, 2, 4, 8, 15]


# --------------------------------------------------------------------------- utils

def log(msg):
    print(f"[deconstruct] {msg}", file=sys.stderr, flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def tc(t):
    """seconds -> H:MM:SS.s or M:SS.s"""
    t = max(0.0, float(t))
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:04.1f}" if h else f"{int(m)}:{s:04.1f}"


def hexcol(rgb):
    r, g, b = (int(max(0, min(255, round(c)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def require(binary):
    if shutil.which(binary) is None:
        sys.exit(f"error: '{binary}' not found on PATH. Install ffmpeg first.")


# ------------------------------------------------------------------------ download

def is_url(s):
    return re.match(r"^https?://", s) is not None


def download(url, outdir, max_h, want_subs):
    dl = os.path.join(outdir, "source")
    os.makedirs(dl, exist_ok=True)
    ytdlp = [sys.executable, "-m", "yt_dlp"]
    if run(ytdlp + ["--version"]).returncode != 0:
        if shutil.which("yt-dlp"):
            ytdlp = ["yt-dlp"]
        else:
            sys.exit("error: yt-dlp is needed for URLs. `pip install yt-dlp`, "
                     "or download the video yourself and pass the file path.")
    fmt = f"bv*[height<={max_h}]+ba/b[height<={max_h}]/bv*+ba/b"
    log(f"downloading {url}")
    r = run(ytdlp + ["-f", fmt, "--merge-output-format", "mp4", "--no-playlist",
                     "--write-info-json", "-o", os.path.join(dl, "video.%(ext)s"), url])
    if r.returncode != 0:
        tail = "\n".join(r.stderr.strip().splitlines()[-6:])
        sys.exit("error: download failed. If this is a network/proxy refusal, the host "
                 "is not reachable from here: get the file another way and pass its path.\n"
                 + tail)
    if want_subs:  # separate pass so caption failures never kill the video download
        run(ytdlp + ["--skip-download", "--no-playlist", "--write-subs", "--write-auto-subs",
                     "--sub-langs", "en.*,en", "--sub-format", "vtt",
                     "-o", os.path.join(dl, "video.%(ext)s"), url])
    vids = [p for p in glob.glob(os.path.join(dl, "video.*"))
            if not p.endswith((".json", ".vtt", ".part", ".ytdl"))]
    if not vids:
        sys.exit("error: yt-dlp finished but no video file was written.")
    info = {}
    ij = os.path.join(dl, "video.info.json")
    if os.path.exists(ij):
        with open(ij, encoding="utf-8") as f:
            raw = json.load(f)
        info = {k: raw.get(k) for k in ("title", "uploader", "channel", "upload_date",
                                         "duration", "description", "webpage_url",
                                         "view_count", "tags", "categories")}
        info["chapters"] = [{"start": c.get("start_time"), "title": c.get("title")}
                            for c in (raw.get("chapters") or [])]
    subs = sorted(glob.glob(os.path.join(dl, "*.vtt")))
    # prefer human captions (video.en.vtt) over auto ones (video.en-orig / en-*.vtt)
    subs.sort(key=lambda p: (0 if re.search(r"\.en\.vtt$", p) else 1, p))
    return vids[0], info, (subs[0] if subs else None)


# --------------------------------------------------------------------------- probe

def probe(path):
    r = run(["ffprobe", "-v", "error", "-print_format", "json",
             "-show_streams", "-show_format", path])
    if r.returncode != 0:
        sys.exit(f"error: ffprobe could not read {path}\n{r.stderr}")
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s.get("codec_type") == "video"), None)
    if v is None:
        sys.exit("error: no video stream found.")
    a = next((s for s in d["streams"] if s.get("codec_type") == "audio"), None)
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    rot = rot or int((v.get("tags") or {}).get("rotate", 0))
    if abs(rot) % 180 == 90:
        w, h = h, w
    sar = v.get("sample_aspect_ratio", "1:1")
    try:
        sn, sd_ = (int(x) for x in sar.split(":"))
        sar_f = sn / sd_ if sn and sd_ else 1.0
    except ValueError:
        sar_f = 1.0

    def rate(s):
        try:
            n, dd = s.split("/")
            return float(n) / float(dd) if float(dd) else 0.0
        except (ValueError, AttributeError):
            return 0.0

    fps = rate(v.get("avg_frame_rate")) or rate(v.get("r_frame_rate")) or 25.0
    dur = float(d["format"].get("duration") or v.get("duration") or 0)
    return {"width": w, "height": h, "display_aspect": round(w * sar_f / h, 4),
            "fps": round(fps, 3), "duration": round(dur, 3),
            "video_codec": v.get("codec_name"), "has_audio": a is not None,
            "audio_codec": a.get("codec_name") if a else None}


# ------------------------------------------------- single-pass decode + cut detect

def _hist(rgb_u8):
    q = (rgb_u8[..., 0] >> 5).astype(np.int32) * 64 + (rgb_u8[..., 1] >> 5) * 8 + (rgb_u8[..., 2] >> 5)
    h = np.bincount(q.ravel(), minlength=512).astype(np.float32)
    return h / h.sum()


def _diff(a, b):
    """cut score between two small uint8 RGB frames: half colour-histogram
    distance, half pixel difference. 0 = identical, ~1 = unrelated."""
    hd = 1.0 - np.minimum(_hist(a), _hist(b)).sum()
    pd = np.abs(a.astype(np.int16) - b.astype(np.int16)).mean() / 255.0
    return 0.5 * hd + 0.5 * min(1.0, pd * 4)


def decode(path, meta, analysis_fps):
    """One ffmpeg pass. Every frame (capped at 30 fps) feeds the cut detector;
    frames on the analysis grid are kept for colour + motion."""
    W = ANALYSIS_W
    H = max(2, int(round(W / meta["display_aspect"] / 2)) * 2)
    dfps = min(meta["fps"] or 25.0, 30.0)
    afps = min(analysis_fps, dfps)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-an", "-sn",
           "-vf", f"fps={dfps:.6f},scale={W}:{H}:flags=area,setsar=1",
           "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    log(f"decoding at {dfps:.2f} fps for cuts, keeping {afps:.2f} fps at {W}x{H} for analysis")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = W * H * 3
    gray, thumbs, stats, kept_t = [], [], [], []
    luma_all, scores, flash_ok = [], [], []
    row_max = np.zeros(H, np.float32)
    col_max = np.zeros(W, np.float32)
    prev2 = prev = None
    i, next_keep = 0, 0.0
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        u8 = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        small = u8[::2, ::2]
        scores.append(_diff(prev, small) if prev is not None else 0.0)
        # flash test: is this frame closer to the one two back than to the previous?
        flash_ok.append(_diff(prev2, small) if prev2 is not None else 1.0)
        prev2, prev = prev, small
        t = i / dfps
        rgb = None
        luma_all.append(float((0.2126 * u8[..., 0] + 0.7152 * u8[..., 1] + 0.0722 * u8[..., 2]).mean() / 255.0))
        if t + 1e-6 >= next_keep:
            next_keep += 1.0 / afps
            rgb = u8.astype(np.float32) / 255.0
            R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
            Y = 0.2126 * R + 0.7152 * G + 0.0722 * B
            mx, mn = rgb.max(2), rgb.min(2)
            sat = np.where(mx > 0.02, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
            sh, hi = Y < 0.25, Y > 0.75
            stats.append([
                Y.mean(), Y.std(), np.percentile(Y, 2), np.percentile(Y, 98),
                sat.mean(), (R - B).mean(), (G - (R + B) / 2).mean(),
                *(rgb[sh].mean(0) if sh.sum() > 20 else (np.nan,) * 3),
                *(rgb[hi].mean(0) if hi.sum() > 20 else (np.nan,) * 3),
                sh.mean(), hi.mean(), *rgb.reshape(-1, 3).mean(0),
            ])
            row_max = np.maximum(row_max, np.percentile(Y, 99, axis=1))
            col_max = np.maximum(col_max, np.percentile(Y, 99, axis=0))
            gray.append((Y * 255).astype(np.uint8))
            thumbs.append(u8[::3, ::3].copy())
            kept_t.append(t)
        i += 1
    p.wait()
    if not gray:
        sys.exit("error: no frames decoded.")
    return {"W": W, "H": H, "fps": afps, "decode_fps": dfps, "gray": np.stack(gray),
            "thumbs": np.stack(thumbs), "stats": np.array(stats, np.float32),
            "t": np.array(kept_t), "row_max": row_max, "col_max": col_max,
            "scores": np.array(scores, np.float32), "flash": np.array(flash_ok, np.float32),
            "luma": np.array(luma_all, np.float32)}


def find_cuts(fr, hard, ratio, floor, min_shot, duration):
    s, fl, dfps = fr["scores"], fr["flash"], fr["decode_fps"]
    n = len(s)
    k = max(4, int(round(dfps / 4)))          # ~0.25 s each side
    cuts = []
    for i in range(1, n):
        if s[i] < floor:
            continue
        lo, hi = max(0, i - k), min(n, i + k + 1)
        if s[i] < s[lo:hi].max():               # keep only the local peak
            continue
        nb = np.concatenate([s[lo:max(lo, i - 1)], s[min(hi, i + 2):hi]])
        base = float(np.median(nb)) if len(nb) else 0.0
        if not (s[i] >= hard or s[i] >= ratio * max(base, 0.02)):
            continue
        # single-frame flash: next frame jumps back to what we had before
        if i + 1 < n and fl[i + 1] < 0.35 * s[i] and s[i + 1] > 0.6 * s[i]:
            continue
        cuts.append((i / dfps, float(s[i]), base))
    kept, last = [], 0.0
    for t, sc, base in cuts:
        if t - last >= min_shot and duration - t >= min_shot:
            kept.append({"t": round(t, 3), "score": round(sc, 3), "baseline": round(base, 3)})
            last = t
    return kept


def find_blacks(fr, min_len=0.08):
    L, dfps = fr["luma"], fr["decode_fps"]
    dark = L < 0.035
    out, i, n = [], 0, len(L)
    while i < n:
        if not dark[i]:
            i += 1
            continue
        j = i
        while j < n and dark[j]:
            j += 1
        if (j - i) / dfps >= min_len:
            w = max(2, int(0.5 * dfps))
            before = L[max(0, i - w):i]
            after = L[j:min(n, j + w)]
            fade_out = len(before) > 2 and before[0] > 0.08 and before[0] > 2.0 * before[-1] \
                and np.all(np.diff(before) <= 0.02)
            fade_in = len(after) > 2 and after[-1] > 0.08 and after[-1] > 2.0 * after[0] \
                and np.all(np.diff(after) >= -0.02)
            out.append({"start": round(i / dfps, 3), "end": round(j / dfps, 3),
                        "in": "fade-out" if fade_out else "cut", "out": "fade-in" if fade_in else "cut"})
        i = j
    return out


STAT_KEYS = ["luma", "contrast", "black_pt", "white_pt", "saturation", "warmth", "tint",
             "sh_r", "sh_g", "sh_b", "hi_r", "hi_g", "hi_b", "sh_frac", "hi_frac",
             "mean_r", "mean_g", "mean_b"]


def letterbox(fr):
    def bars(v):
        dark = v < 0.06
        a = 0
        while a < len(v) // 3 and dark[a]:
            a += 1
        b = 0
        while b < len(v) // 3 and dark[len(v) - 1 - b]:
            b += 1
        return a, b
    t, b = bars(fr["row_max"])
    l, r = bars(fr["col_max"])
    aw, ah = fr["W"] - l - r, fr["H"] - t - b
    return {"bars_top_bottom_pct": round(100 * (t + b) / fr["H"], 1),
            "bars_left_right_pct": round(100 * (l + r) / fr["W"], 1),
            "active_aspect": round(aw / ah, 3) if ah > 0 else None}


# --------------------------------------------------------------------------- motion

def _phase(a, b, win):
    A = np.fft.rfft2((a - a.mean()) * win)
    B = np.fft.rfft2((b - b.mean()) * win)
    R = B * np.conj(A)
    R /= np.abs(R) + 1e-9
    r = np.fft.irfft2(R, s=a.shape)
    iy, ix = np.unravel_index(np.argmax(r), r.shape)
    h, w = r.shape

    def sub(c, m, p):
        d = m - 2 * c + p
        return 0.0 if abs(d) < 1e-9 else 0.5 * (m - p) / d

    dy = iy + sub(r[iy, ix], r[(iy - 1) % h, ix], r[(iy + 1) % h, ix])
    dx = ix + sub(r[iy, ix], r[iy, (ix - 1) % w], r[iy, (ix + 1) % w])
    if dy > h / 2:
        dy -= h
    if dx > w / 2:
        dx -= w
    return dx, dy, float(r[iy, ix])


def shot_motion(gray, fps, W, H):
    """Global translation, zoom and shake from consecutive low-res frames.
    Returns content motion: dx>0 means the image content moves right
    (camera pans/trucks LEFT)."""
    n = len(gray)
    if n < 4:
        return {"label": "too short to read", "pan_fw_s": 0, "tilt_fh_s": 0,
                "zoom_s": 0, "shake": 0, "activity": 0}
    g = gray.astype(np.float32)
    win = np.outer(np.hanning(H), np.hanning(W)).astype(np.float32)
    bh, bw = H // 3, W // 3
    bwin = np.outer(np.hanning(bh), np.hanning(bw)).astype(np.float32)
    centers = [((bx + 0.5) * bw - W / 2, (by + 0.5) * bh - H / 2)
               for by in range(3) for bx in range(3)]
    gdx, gdy, zooms, resid = [], [], [], []
    for i in range(n - 1):
        a, b = g[i], g[i + 1]
        dx, dy, pk = _phase(a, b, win)
        if pk < 0.03:          # untextured / cut / flash: unreliable pair
            continue
        gdx.append(dx)
        gdy.append(dy)
        zs = []
        for k, (cx, cy) in enumerate(centers):
            if k == 4:
                continue
            by, bx = divmod(k, 3)
            sa = a[by * bh:(by + 1) * bh, bx * bw:(bx + 1) * bw]
            sb = b[by * bh:(by + 1) * bh, bx * bw:(bx + 1) * bw]
            tx, ty, bp = _phase(sa, sb, bwin)
            if bp < 0.08:
                continue
            tx, ty = tx - dx, ty - dy
            zs.append((tx * cx + ty * cy) / (cx * cx + cy * cy))
        if len(zs) >= 4:
            zooms.append(float(np.median(zs)))
        sx, sy = int(round(dx)), int(round(dy))
        a2 = a[max(0, -sy):H - max(0, sy), max(0, -sx):W - max(0, sx)]
        b2 = b[max(0, sy):H - max(0, -sy), max(0, sx):W - max(0, -sx)]
        if a2.size:
            resid.append(float(np.abs(a2 - b2).mean()) / 255.0)
    if len(gdx) < 3:
        return {"label": "unreadable (flat/flashing)", "pan_fw_s": 0, "tilt_fh_s": 0,
                "zoom_s": 0, "shake": 0, "activity": 0}
    gdx, gdy = np.array(gdx), np.array(gdy)
    def drift(v):                                  # trimmed mean = net travel, ignores shake
        v = np.sort(v)
        c = len(v) // 10
        return float(v[c:len(v) - c].mean()) if len(v) - 2 * c > 0 else float(v.mean())
    pan = drift(gdx) / W * fps                     # frame-widths per second
    tilt = drift(gdy) / H * fps                    # frame-heights per second
    zoom = float(np.median(zooms)) * fps if zooms else 0.0   # scale change per second
    k = 3
    if len(gdx) > 2 * k:
        ker = np.ones(2 * k + 1) / (2 * k + 1)
        sm_x = np.convolve(np.pad(gdx, k, mode="edge"), ker, "valid")
        sm_y = np.convolve(np.pad(gdy, k, mode="edge"), ker, "valid")
        # long-edge normalisation: same threshold works for landscape and vertical video
        shake = float(np.sqrt(np.mean((gdx - sm_x) ** 2 + (gdy - sm_y) ** 2))) / max(W, H)
    else:
        shake = 0.0
    activity = float(np.median(resid)) if resid else 0.0

    parts = []
    if abs(zoom) > 0.03:
        parts.append("push-in / zoom-in" if zoom > 0 else "pull-out / zoom-out")
    if abs(pan) > 0.025 or abs(tilt) > 0.025:
        if abs(pan) >= abs(tilt):
            parts.append("pan/truck " + ("left" if pan > 0 else "right"))
        else:
            parts.append("tilt/pedestal " + ("up" if tilt > 0 else "down"))
    if shake > 0.0035:
        parts.append("handheld")
    if not parts:
        parts.append("locked-off")
    if activity > 0.04 and abs(zoom) <= 0.03:      # zoom inflates the residual; don't double-count
        parts.append("busy subject motion")
    return {"label": ", ".join(parts), "pan_fw_s": round(pan, 4), "tilt_fh_s": round(tilt, 4),
            "zoom_s": round(zoom, 4), "shake": round(shake, 5), "activity": round(activity, 4)}


# -------------------------------------------------------------------------- colour

def palette(pixels, k=5, iters=12, seed=0):
    px = pixels.reshape(-1, 3).astype(np.float32)
    if len(px) > 6000:
        px = px[np.random.default_rng(seed).choice(len(px), 6000, replace=False)]
    if len(px) < k:
        return []
    rng = np.random.default_rng(seed)
    c = px[[rng.integers(len(px))]]
    for _ in range(1, k):                      # k-means++ seeding
        d = ((px[:, None] - c[None]) ** 2).sum(2).min(1)
        if d.sum() <= 0:
            break
        c = np.vstack([c, px[rng.choice(len(px), p=d / d.sum())]])
    for _ in range(iters):
        lab = ((px[:, None] - c[None]) ** 2).sum(2).argmin(1)
        c = np.array([px[lab == j].mean(0) if (lab == j).any() else c[j]
                      for j in range(len(c))])
    lab = ((px[:, None] - c[None]) ** 2).sum(2).argmin(1)
    share = np.bincount(lab, minlength=len(c)) / len(lab)
    order = np.argsort(-share)
    return [{"hex": hexcol(c[j]), "share": round(float(share[j]), 3)} for j in order]


def summarize_stats(s):
    out = {}
    for i, k in enumerate(STAT_KEYS):
        col = s[:, i]
        col = col[~np.isnan(col)]
        out[k] = round(float(col.mean()), 4) if len(col) else None
    sh = [out["sh_r"], out["sh_g"], out["sh_b"]]
    hi = [out["hi_r"], out["hi_g"], out["hi_b"]]
    out["shadow_tint"] = hexcol([v * 255 for v in sh]) if None not in sh else None
    out["highlight_tint"] = hexcol([v * 255 for v in hi]) if None not in hi else None
    out["mean_color"] = hexcol([out["mean_r"] * 255, out["mean_g"] * 255, out["mean_b"] * 255])
    for k in ("sh_r", "sh_g", "sh_b", "hi_r", "hi_g", "hi_b", "mean_r", "mean_g", "mean_b"):
        out.pop(k)
    return out


def describe_look(g):
    words = []
    L, C, S, Wm = g["luma"], g["contrast"], g["saturation"], g["warmth"]
    words.append("low-key / dark" if L < 0.28 else "high-key / bright" if L > 0.6 else "mid-key")
    words.append("high contrast" if C > 0.24 else "flat / low contrast" if C < 0.13 else "moderate contrast")
    words.append("desaturated" if S < 0.18 else "punchy saturation" if S > 0.45 else "natural saturation")
    words.append("warm" if Wm > 0.04 else "cool" if Wm < -0.04 else "neutral white balance")
    if g["black_pt"] is not None and g["black_pt"] > 0.07:
        words.append("lifted blacks (matte)")
    if g["black_pt"] is not None and g["black_pt"] < 0.01:
        words.append("crushed blacks")
    if g["white_pt"] is not None and g["white_pt"] > 0.97:
        words.append("hot / clipped highlights")
    if g["white_pt"] is not None and g["white_pt"] < 0.8:
        words.append("rolled-off highlights")
    return ", ".join(words)


def split_tone(g):
    def hue_bias(hx):
        if not hx:
            return None
        r, gg, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
        m = (r + gg + b) / 3
        dr, dg, db = r - m, gg - m, b - m
        if max(abs(dr), abs(dg), abs(db)) < 4:
            return "neutral"
        names = []
        if db > 4 and dg > -2:
            names.append("teal/cyan" if dg > 0 else "blue")
        if dr > 4:
            names.append("orange/amber" if dg >= 0 else "red/magenta")
        if dg > 4 and dr <= 4 and db <= 4:
            names.append("green")
        if db > 4 and dr > 4 and dg < 0:
            names = ["magenta/purple"]
        return "/".join(names) or "neutral"
    return {"shadows": hue_bias(g["shadow_tint"]), "highlights": hue_bias(g["highlight_tint"])}


# --------------------------------------------------------------------------- audio

def analyze_audio(path, cuts, duration):
    sr = 11025
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-vn",
                        "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                       capture_output=True)
    x = np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0
    if len(x) < sr:
        return None
    hop, nfft = 256, 1024
    nfr = 1 + (len(x) - nfft) // hop
    if nfr < 8:
        return None
    idx = np.arange(nfft)[None, :] + hop * np.arange(nfr)[:, None]
    frames = x[idx] * np.hanning(nfft)[None, :]
    mag = np.log1p(10 * np.abs(np.fft.rfft(frames, axis=1)))
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(1)
    flux = np.concatenate([[0], flux])
    env = (flux - flux.mean()) / (flux.std() + 1e-9)
    fr = sr / hop
    w = int(fr)                                   # ~1 s adaptive threshold
    pad = np.pad(env, w, mode="edge")
    csum = np.cumsum(np.concatenate([[0], pad]))
    local = (csum[2 * w + 1:] - csum[:-2 * w - 1]) / (2 * w + 1)
    centre = nfft / 2 / sr
    onsets = [i / fr + centre for i in range(3, len(env) - 3)
              if env[i] == env[i - 3:i + 4].max() and env[i] > local[i] + 1.0]
    # tempo from onset-envelope autocorrelation, 60-190 bpm
    e = np.maximum(env, 0)
    ac = np.correlate(e, e, "full")[len(e) - 1:]
    lo, hi = int(fr * 60 / 190), int(fr * 60 / 60)
    tempo, conf = None, 0.0
    if hi < len(ac):
        lag = lo + int(np.argmax(ac[lo:hi]))
        a0, a1, a2 = ac[lag - 1], ac[lag], ac[lag + 1]
        den = a0 - 2 * a1 + a2
        flag = lag + (0.5 * (a0 - a2) / den if abs(den) > 1e-9 else 0.0)
        tempo = round(60 * fr / flag, 1)
        conf = round(float(ac[lag] / (ac[lo:hi].mean() + 1e-9)), 2)
    # loudness
    blk = int(sr * 0.5)
    rms = np.array([np.sqrt(np.mean(x[i:i + blk] ** 2) + 1e-12) for i in range(0, len(x) - blk, blk)])
    db = 20 * np.log10(rms + 1e-9)
    # cut / onset sync vs chance
    win = 0.06
    on = np.array(onsets)
    sync, chance = None, None
    if len(cuts) and len(on):
        d = np.array([np.abs(on - c).min() for c in cuts])
        sync = round(float((d <= win).mean()), 3)
        chance = round(float(min(1.0, len(on) / max(duration, 1e-6) * 2 * win)), 3)
    return {"tempo_bpm": tempo, "tempo_confidence": conf,
            "onsets_per_min": round(len(onsets) / max(duration, 1e-6) * 60, 1),
            "loudness_dbfs_mean": round(float(db.mean()), 1),
            "loudness_range_db": round(float(np.percentile(db, 95) - np.percentile(db, 10)), 1),
            "silence_pct": round(100 * float((db < -45).mean()), 1),
            "cuts_on_onset": sync, "cuts_on_onset_by_chance": chance,
            "loudness_curve_db": [round(float(v), 1) for v in db[::max(1, len(db) // 60)]]}


# ---------------------------------------------------------------------- transcript

def parse_vtt(path):
    lines_out, last = [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    for block in re.split(r"\n\s*\n", txt):
        m = re.search(r"(\d+:)?(\d+):(\d+\.\d+)\s+-->", block)
        if not m:
            continue
        h = int(m.group(1)[:-1]) if m.group(1) else 0
        t = h * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        body = block[m.end():].split("\n", 1)[1] if "\n" in block[m.end():] else ""
        for ln in body.splitlines():
            ln = re.sub(r"<[^>]+>", "", ln).replace("&amp;", "&").replace("&gt;", ">").replace("&lt;", "<").strip()
            if ln and ln != last:
                lines_out.append((round(t, 2), ln))
                last = ln
    return lines_out


# ----------------------------------------------------------------- keyframes/sheet

def grab(path, t, out, width=480):
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", path,
         "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", out])
    return os.path.exists(out)


def contact_sheets(shots, outdir, cols=5, rows=6, tile_w=300):
    try:
        font = ImageFont.load_default(size=13)
    except TypeError:
        font = ImageFont.load_default()
    per = cols * rows
    paths = []
    for si in range(0, len(shots), per):
        chunk = shots[si:si + per]
        tiles = []
        for s in chunk:
            p = s["frames"].get("mid")
            try:
                im = Image.open(os.path.join(outdir, p)).convert("RGB") if p else None
            except OSError:
                im = None
            if im is None:
                im = Image.new("RGB", (tile_w, int(tile_w * 9 / 16)), (40, 40, 40))
            im = im.resize((tile_w, max(1, int(im.height * tile_w / im.width))))
            tiles.append((s, im))
        th = max(im.height for _, im in tiles)
        lab = 34
        n_rows = math.ceil(len(tiles) / cols)
        sheet = Image.new("RGB", (cols * (tile_w + 6) + 6, n_rows * (th + lab + 6) + 6), (16, 16, 16))
        d = ImageDraw.Draw(sheet)
        for k, (s, im) in enumerate(tiles):
            x = 6 + (k % cols) * (tile_w + 6)
            y = 6 + (k // cols) * (th + lab + 6)
            sheet.paste(im, (x, y))
            d.text((x + 2, y + th + 2), f"#{s['n']:03d}  {tc(s['start'])}  {s['dur']:.1f}s",
                   fill=(235, 235, 235), font=font)
            d.text((x + 2, y + th + 17), s["motion"]["label"][:44], fill=(160, 200, 255), font=font)
        name = f"contact_{si // per + 1:02d}.jpg"
        sheet.save(os.path.join(outdir, name), quality=88)
        paths.append(name)
    return paths


def barcode(fr, cuts, duration, outdir, width=1400, height=160):
    means = fr["stats"][:, -3:]
    n = len(means)
    img = np.zeros((height, width, 3), np.uint8)
    for x in range(width):
        a = int(x / width * n)
        b = max(a + 1, int((x + 1) / width * n))
        img[:, x] = (means[a:b].mean(0) * 255).clip(0, 255)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    for c in cuts:
        x = int(c["t"] / max(duration, 1e-6) * width)
        d.line([(x, height - 14), (x, height)], fill=(255, 255, 255))
    im.save(os.path.join(outdir, "barcode.png"))
    return "barcode.png"


# ---------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="video file path or URL")
    ap.add_argument("-o", "--out", help="output folder (default: ./deconstruct/<name>)")
    ap.add_argument("--sensitivity", type=float, default=3.0,
                    help="a cut must score this many times the local baseline (lower = more cuts). default 3.0")
    ap.add_argument("--hard", type=float, default=0.45,
                    help="any frame change scoring above this (0-1) is a cut regardless of baseline. default 0.45")
    ap.add_argument("--floor", type=float, default=0.10,
                    help="changes scoring below this (0-1) are never cuts. default 0.10")
    ap.add_argument("--min-shot", type=float, default=0.10, help="ignore cuts closer than this (s)")
    ap.add_argument("--fps", type=float, default=12.0, help="analysis frame rate (auto-lowered for long videos)")
    ap.add_argument("--max-height", type=int, default=720, help="download resolution cap for URLs")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--subs", help="path to a .vtt caption file to use")
    args = ap.parse_args()
    require("ffmpeg")
    require("ffprobe")

    if is_url(args.source):
        base = re.sub(r"[^A-Za-z0-9_-]+", "_", args.source.split("v=")[-1].split("/")[-1])[:40] or "video"
    else:
        base = os.path.splitext(os.path.basename(args.source))[0]
    outdir = os.path.abspath(args.out or os.path.join("deconstruct", base))
    os.makedirs(os.path.join(outdir, "frames"), exist_ok=True)

    info, vtt = {}, args.subs
    if is_url(args.source):
        path, info, dl_vtt = download(args.source, outdir, args.max_height, not args.no_subs)
        vtt = vtt or dl_vtt
    else:
        path = os.path.abspath(args.source)
        if not os.path.exists(path):
            sys.exit(f"error: {path} does not exist")
        if not vtt and not args.no_subs:
            side = os.path.splitext(path)[0] + ".vtt"
            vtt = side if os.path.exists(side) else None

    meta = probe(path)
    dur = meta["duration"]
    log(f"{meta['width']}x{meta['height']} @ {meta['fps']} fps, {dur:.1f}s")

    fps = args.fps
    if dur * fps > MAX_ANALYSIS_FRAMES:
        fps = max(2.0, MAX_ANALYSIS_FRAMES / dur)
    fr = decode(path, meta, fps)
    fps = fr["fps"]
    nfr = len(fr["gray"])
    cuts = find_cuts(fr, args.hard, args.sensitivity, args.floor, args.min_shot, dur)
    blacks = find_blacks(fr)

    bounds = [0.0] + [c["t"] for c in cuts] + [dur]
    shots = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        ia = min(nfr - 1, int(math.ceil((a + 0.05) * fps)))
        ib = max(ia + 1, min(nfr, int(math.floor((b - 0.05) * fps)) + 1))
        st = fr["stats"][ia:ib]
        col = summarize_stats(st)
        th = fr["thumbs"][ia:ib]
        pick = th[np.linspace(0, len(th) - 1, min(len(th), 6)).astype(int)] if len(th) else th
        shots.append({
            "n": i + 1, "start": round(a, 3), "end": round(b, 3), "dur": round(b - a, 3),
            "cut_score": cuts[i - 1]["score"] if i > 0 else None,
            "color": col, "palette": palette(pick, k=4) if len(pick) else [],
            "motion": (shot_motion(fr["gray"][ia:ib], fps, fr["W"], fr["H"])
                       if (col["luma"] or 0) > 0.04 else
                       {"label": "black", "pan_fw_s": 0, "tilt_fh_s": 0, "zoom_s": 0, "shake": 0, "activity": 0}),
            "frames": {}, "dialogue": [],
        })

    log(f"{len(shots)} shots; extracting keyframes")
    jobs = []
    for s in shots:
        a, d = s["start"], s["dur"]
        marks = {"mid": a + d / 2}
        if d >= 3.0:
            marks["start"] = a + min(0.25, d * 0.1)
            marks["end"] = a + d - min(0.25, d * 0.1)
        for k, t in marks.items():
            rel = f"frames/shot_{s['n']:03d}_{k}.jpg"
            jobs.append((s, k, t, rel))
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(lambda j: grab(path, j[2], os.path.join(outdir, j[3])), jobs))
    for (s, k, _, rel), ok in zip(jobs, res):
        if ok:
            s["frames"][k] = rel

    transcript = parse_vtt(vtt) if vtt and os.path.exists(vtt) else []
    for t, ln in transcript:
        for s in shots:
            if s["start"] <= t < s["end"]:
                s["dialogue"].append(ln)
                break
    if transcript:
        with open(os.path.join(outdir, "transcript.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(f"[{tc(t)}] {ln}" for t, ln in transcript))

    audio = None
    if meta["has_audio"] and not args.no_audio:
        log("analysing audio")
        audio = analyze_audio(path, [c["t"] for c in cuts], dur)

    # ---- global summaries
    durs = np.array([s["dur"] for s in shots])
    edges = [0] + SHOT_LEN_BUCKETS + [1e9]
    hist = {}
    for lo, hi in zip(edges[:-1], edges[1:]):
        key = f"{lo}-{hi}s" if hi < 1e9 else f">{lo}s"
        hist[key] = int(((durs >= lo) & (durs < hi)).sum())
    seg = dur / 10 if dur > 0 else 1
    pace = []
    for k in range(10):
        n = sum(1 for c in cuts if k * seg <= c["t"] < (k + 1) * seg)
        pace.append(round(n / seg * 60, 1))
    labels = {}
    for s in shots:
        for part in s["motion"]["label"].split(", "):
            labels.setdefault(part, [0, 0.0])
            labels[part][0] += 1
            labels[part][1] += s["dur"]
    motion_mix = {k: {"shots": v[0], "screen_time_pct": round(100 * v[1] / max(dur, 1e-6), 1)}
                  for k, v in sorted(labels.items(), key=lambda kv: -kv[1][1])}
    gcol = summarize_stats(fr["stats"])
    words = sum(len(ln.split()) for _, ln in transcript)

    analysis = {
        "source": args.source, "file": path, "info": info, "meta": meta,
        "analysis_fps": round(fps, 3), "frame": letterbox(fr),
        "editing": {
            "shots": len(shots), "cuts": len(cuts),
            "asl_s": round(float(durs.mean()), 3), "median_shot_s": round(float(np.median(durs)), 3),
            "shortest_s": round(float(durs.min()), 3), "longest_s": round(float(durs.max()), 3),
            "cuts_per_min": round(len(cuts) / max(dur, 1e-6) * 60, 2),
            "shot_length_hist": hist, "pace_curve_cuts_per_min_by_decile": pace,
            "black_segments": blacks,
            "detector": {"sensitivity": args.sensitivity, "hard": args.hard, "floor": args.floor,
                         "decode_fps": round(fr["decode_fps"], 3)},
        },
        "color": {**gcol, "look": describe_look(gcol), "split_tone": split_tone(gcol),
                  "palette": palette(fr["thumbs"][np.linspace(0, nfr - 1, min(nfr, 40)).astype(int)], k=6)},
        "motion_mix": motion_mix,
        "audio": audio,
        "speech": {"lines": len(transcript), "words": words,
                   "words_per_min": round(words / max(dur, 1e-6) * 60, 1) if words else 0},
        "shots": shots,
    }
    analysis["contact_sheets"] = contact_sheets(shots, outdir)
    analysis["barcode"] = barcode(fr, cuts, dur, outdir)
    with open(os.path.join(outdir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=1)
    write_report(analysis, outdir)
    log(f"done -> {outdir}")
    print(outdir)


def write_report(a, outdir):
    m, e, c, fr = a["meta"], a["editing"], a["color"], a["frame"]
    L = []
    title = (a["info"] or {}).get("title") or os.path.basename(a["file"])
    L.append(f"# Deconstruction: {title}\n")
    inf = a["info"] or {}
    if inf:
        L.append(f"- Channel: {inf.get('channel') or inf.get('uploader')}  |  Uploaded: {inf.get('upload_date')}  |  URL: {inf.get('webpage_url')}")
    L.append(f"- Runtime {tc(m['duration'])}  |  {m['width']}x{m['height']}  |  {m['fps']} fps  |  "
             f"display aspect {m['display_aspect']:.3f}  |  active picture aspect {fr['active_aspect']} "
             f"(bars T/B {fr['bars_top_bottom_pct']}%, L/R {fr['bars_left_right_pct']}%)")
    L.append("\n> Numbers are heuristics from a low-res pass. Verify every claim against the contact sheets and frames before putting it in a style profile.\n")

    L.append("## Editing rhythm")
    L.append(f"- {e['shots']} shots, {e['cuts']} cuts, **ASL {e['asl_s']:.2f}s** (median {e['median_shot_s']:.2f}s, "
             f"range {e['shortest_s']:.2f}-{e['longest_s']:.2f}s), **{e['cuts_per_min']} cuts/min**")
    L.append(f"- Shot-length histogram: " + ", ".join(f"{k}: {v}" for k, v in e["shot_length_hist"].items()))
    L.append(f"- Pace curve (cuts/min per 10% of runtime): {e['pace_curve_cuts_per_min_by_decile']}")
    if e["black_segments"]:
        L.append(f"- Black segments: " + ", ".join(
            f"{tc(b['start'])}-{tc(b['end'])} ({b['in']} → black → {b['out']})" for b in e["black_segments"][:20]))
    d = e["detector"]
    L.append(f"- Cut detector: sensitivity {d['sensitivity']}, hard {d['hard']}, floor {d['floor']} at {d['decode_fps']} fps. "
             "Dissolves, whip-pans and match cuts can slip through or split; check the frames.\n")

    L.append("## Colour & exposure")
    L.append(f"- Look: **{c['look']}**")
    L.append(f"- Mean luma {c['luma']:.2f}, contrast (luma SD) {c['contrast']:.2f}, black point {c['black_pt']:.3f}, "
             f"white point {c['white_pt']:.3f}, saturation {c['saturation']:.2f}, warmth (R-B) {c['warmth']:+.3f}, tint (G-RB) {c['tint']:+.3f}")
    L.append(f"- Split tone: shadows {c['split_tone']['shadows']} ({c['shadow_tint']}), highlights {c['split_tone']['highlights']} ({c['highlight_tint']})")
    L.append(f"- Global palette: " + "  ".join(f"`{p['hex']}` {int(p['share']*100)}%" for p in c["palette"]))
    L.append(f"- Colour-over-time strip: `{a['barcode']}`\n")

    L.append("## Camera motion mix")
    for k, v in a["motion_mix"].items():
        L.append(f"- {k}: {v['shots']} shots, {v['screen_time_pct']}% of runtime")
    L.append("")

    au = a["audio"]
    L.append("## Sound & music sync")
    if au:
        L.append(f"- Tempo ≈ {au['tempo_bpm']} bpm (confidence {au['tempo_confidence']}), {au['onsets_per_min']} onsets/min")
        L.append(f"- Loudness mean {au['loudness_dbfs_mean']} dBFS, range {au['loudness_range_db']} dB, silence {au['silence_pct']}%")
        if au["cuts_on_onset"] is not None:
            L.append(f"- Cuts landing on an audio onset (±60 ms): {int(au['cuts_on_onset']*100)}% vs {int(au['cuts_on_onset_by_chance']*100)}% expected by chance")
    else:
        L.append("- No audio analysed.")
    sp = a["speech"]
    L.append(f"- Speech: {sp['lines']} caption lines, {sp['words']} words, {sp['words_per_min']} words/min\n")

    if inf.get("chapters"):
        L.append("## Chapters")
        for ch in inf["chapters"]:
            L.append(f"- {tc(ch['start'] or 0)} {ch['title']}")
        L.append("")
    if inf.get("description"):
        L.append("## Description (from the platform, verbatim)\n")
        L.append("```\n" + inf["description"][:3000] + "\n```\n")

    L.append("## Contact sheets (look at these)")
    for p in a["contact_sheets"]:
        L.append(f"- `{p}`")
    L.append("")
    L.append("## Shot table")
    L.append("| # | in | dur | motion | luma | sat | warm | palette | dialogue |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for s in a["shots"]:
        col = s["color"]
        pal = " ".join(p["hex"] for p in s["palette"][:3])
        dlg = " / ".join(s["dialogue"])[:80].replace("|", "/")
        L.append(f"| {s['n']} | {tc(s['start'])} | {s['dur']:.2f} | {s['motion']['label']} | "
                 f"{col['luma']:.2f} | {col['saturation']:.2f} | {col['warmth']:+.2f} | {pal} | {dlg} |")
    with open(os.path.join(outdir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
