"""Solve the depth (x) of every traced header point so the near-bank primaries are physically
possible, while each point stays exactly on its photo-13 pixel (it slides along its camera ray).

Inputs: a JSON dump of the built headers (tools/dump_headers.py, run with the bpy module) with
  cam (photo-13 camera), root_z, tubes{ci: p0, p1, collector, uv[], bell[], anchors, r}
Constraints / costs:
  * top-view envelope (photo 20, perspective-corrected): centreline x >= X_OUT
  * stay clear of the head face: x <= X_IN
  * smooth along each tube (1st + 2nd differences)
  * tube-to-tube and tube-to-itself clearance >= OD + GAP, evaluated on the real curve Blender
    draws (order-4 clamped uniform NURBS through the control points), except near the collector
  * weak pull of the bellows midpoints to the triangulated landmarks
usage: python solve_header_depth.py hdr.json out_anchors.json
"""
import sys, json
import numpy as np
from scipy.optimize import least_squares

X_OUT, X_IN = -360.0, -282.0          # mm; envelope from top photo 20 (outer surface ~-378)
GAP = 4.0                             # mm between tube surfaces
SKIP_NEAR_COLLECTOR = 70.0            # merge region: tubes legitimately meet
BELLOWS_PRIOR = {5: -326.0, 0: -309.0}   # header_landmarks_ba.json rear / front bellows x
# starting layout that already respects the stacking order seen in photo 13 / video 20.8 s
# (the solver then only has to resolve clearances locally)
INIT_HINT = {5: [-345] * 7,
             4: [-300, -300, -302, -304, -306, -312, -318, -324, -328, -330],
             3: [-284, -284, -286, -305, -330, -338, -340, -336, -328],
             2: [-296, -300, -310, -322, -332, -336, -336, -334],
             1: [-298, -302, -310, -318, -326, -332, -336, -338, -336, -334],
             0: [-284, -288, -292, -298, -302, -306, -308, -310, -312]}
# who hides whom in side photo 13 (camera on -X, so the tube in front has the more negative x):
# (front tube, its trace points, back tube, its trace points, min x separation mm)
OCCLUSION = [(3, [4, 5, 6, 7], 4, [1, 2, 3, 4], 15.0),   # cyl-4 front arch over the cyl-5 upper arch
             (5, [2, 3, 4, 5], 3, [0, 1, 2], 15.0),      # cyl-6 bellows tube hides the cyl-4 rearward run
             (1, [6, 7, 8], 0, [5, 6, 7], 10.0)]         # cyl-2 long run in front of the cyl-1 drop


def ray_fn(cam, root_z):
    R = np.array(cam["rot"]); L = np.array(cam["loc"]) * 1000.0
    W, H = cam["size"]; f = cam["lens"] / 36.0 * W

    def at(u, v, x):
        d = R @ np.array([(u - W / 2) / f, -(v - H / 2) / f, -1.0])
        t = (x - L[0]) / d[0]
        q = L + d * t
        return np.array([x, q[1], q[2] - root_z])
    return at


def bspline_basis(m, n=90, k=4):
    """basis matrix (n x m) of a clamped uniform B-spline (Blender NURBS, endpoint on, weights 1)"""
    k = min(k, m)
    kv = np.concatenate([np.zeros(k), np.arange(1, m - k + 1), np.full(k, m - k + 1)]).astype(float)
    ts = np.linspace(0, kv[-1] - 1e-9, n)
    rows = []
    for t in ts:
        N = np.array([1.0 if kv[i] <= t < kv[i + 1] else 0.0 for i in range(len(kv) - 1)])
        for d in range(2, k + 1):
            N2 = np.zeros(len(kv) - d)
            for i in range(len(kv) - d):
                a = (t - kv[i]) / (kv[i + d - 1] - kv[i]) * N[i] if kv[i + d - 1] > kv[i] else 0.0
                b = (kv[i + d] - t) / (kv[i + d] - kv[i + 1]) * N[i + 1] if kv[i + d] > kv[i + 1] else 0.0
                N2[i] = a + b
            N = N2
        rows.append(N[:m])
    return np.array(rows)


def main():
    D = json.load(open(sys.argv[1]))
    at = ray_fn(D["cam"], D["root_z"])
    tubes = {int(k): v for k, v in D["tubes"].items()}
    far = bool(D.get("far"))
    global X_OUT, X_IN
    if far:                                  # far bank: mirrored envelope, no near-bank stacking/priors
        X_OUT, X_IN = -X_OUT + 6.0, -X_IN   # far envelope not yet measured in photo 20: +366 / +282
        global GAP
        GAP = 7.0                            # fat merged sections: Blender's radius interpolation runs larger
        OCC, HINT, BPRI = [], {}, {}
    else:
        OCC, HINT, BPRI = OCCLUSION, INIT_HINT, BELLOWS_PRIOR
    merged = {ci: t.get("merge_into") for ci, t in tubes.items()}
    col = np.array(next(t["collector"] for ci, t in tubes.items() if merged[ci] is None))
    cis = sorted(tubes)
    # initial depths: current anchors interpolated, clipped into the envelope
    x0, idx = [], {}
    for ci in cis:
        t = tubes[ci]
        anc = {int(k): v for k, v in t["anchors"].items()}
        anc.setdefault(-1, 292.0 if far else -292.0); anc.setdefault(len(t["uv"]), col[0])
        keys = sorted(anc)
        for j in range(len(t["uv"])):
            k0 = max(k for k in keys if k <= j); k1 = min(k for k in keys if k >= j)
            s = 0 if k1 == k0 else (j - k0) / (k1 - k0)
            idx[(ci, j)] = len(x0)
            if ci in HINT and len(HINT[ci]) == len(t["uv"]):
                x0.append(float(HINT[ci][j]))
            else:
                lo_, hi_ = sorted((X_OUT, X_IN))
                x0.append(float(np.clip(anc[k0] + (anc[k1] - anc[k0]) * s, lo_ + 2, hi_ - 2)))
    x0 = np.array(x0)

    def nctrl(ci):
        return len(tubes[ci]["uv"]) + (3 if merged[ci] is not None else 4)
    BAS = {ci: bspline_basis(nctrl(ci)) for ci in cis}
    RAD = {ci: BAS[ci] @ np.array(tubes[ci]["radii"][:nctrl(ci)]) for ci in cis}   # radius per sample

    def curves(x):
        C = {}
        for ci in cis:
            t = tubes[ci]
            pts = [at(u, v, x[idx[(ci, j)]]) for j, (u, v) in enumerate(t["uv"])]
            p0, p1 = np.array(t["p0"]), np.array(t["p1"])
            ctrl = [p0, p1, (p1 + pts[0]) / 2] + pts + ([] if merged[ci] is not None else [col])
            C[ci] = (BAS[ci] @ np.array(ctrl), pts)
        return C

    def keep_mask(S):
        K = {ci: np.linalg.norm(S[ci] - col, axis=1) > SKIP_NEAR_COLLECTOR for ci in cis}
        for ci in cis:                       # a merged tube's last stretch is inside its partner
            if merged[ci] is not None:
                K[ci] &= np.linalg.norm(S[ci] - S[ci][-1], axis=1) > 60.0
        return K

    def resid(x):
        res = []
        for ci in cis:
            n = len(tubes[ci]["uv"])
            xs = np.array([x[idx[(ci, j)]] for j in range(n)])
            res += list(np.diff(xs) * 0.15)
            if merged[ci] is None:                       # arrive at the collector without a kink
                res.append((xs[-1] - col[0]) * 0.25)
                res.append((xs[-2] - col[0]) * 0.1)
            res += list(np.diff(xs, 2) * 0.3)
            lo_, hi_ = sorted((X_OUT, X_IN))
            if far:   # photo 20: far bundle edge ~+345 apparent (~+360 true) ahead of the catalyst (y < 300)
                ys_ = np.array([at(u, v, x[idx[(ci, j)]])[1] for j, (u, v) in enumerate(tubes[ci]["uv"])])
                hi_ = np.where(ys_ < 300.0, 342.0, hi_)
            res += list(np.maximum(0, lo_ - xs) * 3.0)
            res += list(np.maximum(0, xs - hi_) * 3.0)
            if ci in BPRI:
                i0, i1 = tubes[ci]["bell"][0]
                res.append(((xs[i0] + xs[i1]) / 2 - BPRI[ci]) * 0.2)
        for fc, fj, bc, bj, m in OCC:
            if fc in tubes and bc in tubes:
                xf = np.mean([x[idx[(fc, j)]] for j in fj if (fc, j) in idx])
                xb = np.mean([x[idx[(bc, j)]] for j in bj if (bc, j) in idx])
                res.append(max(0.0, xf - (xb - m)) * 3.0)
        C = curves(x)
        S = {ci: C[ci][0] for ci in cis}
        keep = keep_mask(S)
        for a in range(len(cis)):
            A = S[cis[a]]
            for b in range(a, len(cis)):
                B = S[cis[b]]
                lim = RAD[cis[a]][:, None] + RAD[cis[b]][None, :] + GAP
                Dm = np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)
                Dm = np.where(keep[cis[a]][:, None] & keep[cis[b]][None, :], Dm, 1e9)
                if a == b:                                  # self: only far-apart parts of the tube
                    seg = np.cumsum(np.r_[0, np.linalg.norm(np.diff(A, axis=0), axis=1)])
                    apart = np.abs(seg[:, None] - seg[None, :]) > 3.5 * lim
                    Dm = np.where(apart, Dm, 1e9)
                v = np.maximum(0, (lim - Dm)).max(axis=1)
                res += list(v * 2.0)
        return np.array(res)

    sol = least_squares(resid, x0, method="trf", diff_step=1e-3, max_nfev=300, verbose=0)
    x = sol.x
    C = curves(x)
    print("cost %.1f -> %.1f" % (0.5 * (resid(x0) ** 2).sum(), sol.cost))
    out = {}
    S = {ci: C[ci][0] for ci in cis}
    K = keep_mask(S)
    for ci in cis:
        n = len(tubes[ci]["uv"])
        out[ci] = {j: round(float(x[idx[(ci, j)]]), 1) for j in range(n)}
        gaps = []
        for c in cis:
            if c == ci:
                continue
            Dm = np.linalg.norm(S[ci][:, None] - S[c][None], axis=2) - RAD[ci][:, None] - RAD[c][None, :]
            Dm = np.where(K[ci][:, None] & K[c][None, :], Dm, 1e9)
            gaps.append(Dm.min())
        print("ci %d r %.1f depths %s   min surface gap to other tubes %.1f mm" % (
            ci, RAD[ci].min(), " ".join("%.0f" % out[ci][j] for j in range(n)), min(gaps)))
    json.dump({str(k): {str(j): v for j, v in d.items()} for k, d in out.items()}, open(sys.argv[2], "w"), indent=1)


if __name__ == "__main__":
    main()
