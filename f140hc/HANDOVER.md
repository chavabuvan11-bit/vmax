# F140HC (Daytona SP3 V12): handover

Read this first if you're a new chat picking up the work. Everything needed to continue is in
this repo, apart from one user-uploaded video (see "References").

## 1. What the user wants

- **Goal:** a Blender model of the Ferrari Daytona SP3's F140HC 6.5 L V12 (with gearbox and
  exhaust) that looks **photorealistic and 1:1**, with **working internals**.
- **How they want it done:**
  1. Don't trust a single photo. Work out each part's shape from **many views**: the Amalgam
     photos, the Amalgam reveal video, and internet pictures of each individual part.
  2. **Common-sense check every part.** Nothing floats, every tube end connects, every bolt sits
     on a surface, belts touch their pulleys. Run `tools/sanity.py` and keep it passing.
  3. Focus on one section until it's genuinely right, then move to the next.
  4. They no longer need progress pictures. Work for the best result.
- **Current focus section:** the near-side lower engine, as seen in Amalgam photo 13 rows
  596–1196. That's the −X bank (cylinders 1-6) header bundle, catalyst (dome, canister, outlet
  cone), V-band clamp, alternator, oil and water pump castings, and the gearbox's
  differential side cover. After this, "continue with the rest" of the engine.
- **The user's style:** direct and honest. They care about real accuracy over speed and are
  happy to supply references (they uploaded the video). Don't do "sassy AI".

## 2. Repo layout and commands

```
f140hc/f140hc_build.py   the model. Everything derives from the P table at the top
f140hc/verify.py         mechanism checks (6) + optional renders: --render DIR --shots a,b
f140hc/tools/sanity.py   common-sense checks: floating / loose tube ends / unseated bolts / belt
f140hc/tools/*.py        measurement, camera solving, fitting and render tools (see section 5)
f140hc/reference_data/   solved cameras, picked points, measurements, Amalgam product JSON
f140hc/README.md         user-facing readme (older; refresh when the section is done)
```

Setup in a fresh session (the cloud scratchpad does NOT persist):

```bash
bash f140hc/tools/setup_refs.sh                      # creates ./f140_work (git-ignored)
export F140_REFS=$PWD/f140_work/refs F140_HDRI=$PWD/f140_work/refs/hdri/photo_studio_01_2k.hdr
f140_work/bpyenv/bin/python -I f140hc/verify.py       # must print PASS
f140_work/bpyenv/bin/python -I f140hc/tools/sanity.py # must print SANITY: PASS
```

Section comparison: render the model through the solved photo-13 camera and stack it under the
photo crop.

```bash
F140_HDRI=$F140_HDRI f140_work/bpyenv/bin/python -I f140hc/tools/render_section.py f140hc/reference_data/cameras/ba_photo13_camera.json out.png 500 1200 48
python3 f140hc/tools/compare_section.py $F140_REFS/amalgam/13.jpg out.png 596 1196 cmp.jpg
```

Always set `F140_HDRI`. Without it the render uses the fallback lights and the polished steel
reads dark, which is misleading.

Other views: `tools/fit_view.py SPEC.json OUTDIR` solves that photo's camera from the picked
points, renders the model from it, and writes `compare.jpg` (photo with pick markers | render).
Specs are in `reference_data/specs/`. Their photo paths are relative to `$F140_REFS`.

## 3. Conventions

- **Units:** the build is authored in mm (the `P` table). Blender stores metres (`MM = 0.001`).
- **Root frame:** `F140HC_ROOT` sits at world z = 150 mm. The crank axis is the root's origin
  and runs along +Y, with Y = 0 at the block front. **Front of engine = −Y** (timing, belt,
  alternator); the gearbox is at +Y.
- **Banks:**
  - `Bank_1-6` sits at γ = −32.5° on the −X side and is staggered **rearward** by
    `bank_offset` (23 mm). Its cylinders are at y = 85 + 104k.
  - `Bank_7-12` sits at γ = +32.5° on the +X side, with cylinders at y = 62 + 104k.
  - The alternator is on −X and the A/C compressor on +X (front photo 11).
- **Near-bank coordinates:** the exhaust code is written in −X bank coordinates. `W()` mirrors
  X and shifts Y by −23 mm for bank 7-12.
- **Photo 13 near-orthographic mapping,** used for tracing: y = 605 − (u − 513)·0.730 and
  z = 199 − (v − 600)·0.737, for 1800×1200 pixels.
- **Top photo 20 mapping:** y = 677 − (u − 947)·1.257 and x = −(v − 599)·1.325. The ruler is the
  cam cover: half-width 206 px = 273 mm.
- **Camera JSON format:** `{lens (mm, 36 mm sensor, horizontal fit), loc (world m), rot (3×3,
  columns = camera X, Y, Z axes in world; Blender −Z is forward)}`.

## 4. References

- **Amalgam 1:4 SP3 engine and gearbox,** built "using original CAD designs … from Ferrari".
  The 23 photos are fetched by `setup_refs.sh` as `refs/amalgam/01..23.jpg`.
  - **Photos used as reference:**
    - 13: side, −X bank, near-level camera. The primary target.
    - 20: straight top-down view.
    - 11: front, near-orthographic.
    - 10: rear.
    - 16 and 08: low front three-quarter close-ups of the +X bank (mirror these).
    - 12, 04, 05, 01: full side and three-quarter views.
    - 07: gearbox side close-up.
    - 19: rear three-quarter from above.
    - 09: cover and pods close-up.
    - 14 and 15: gearbox top.
    - 17: front accessory close-up.
    - 18: mufflers.
  - **Not useful:** 21–23 (display case, packaging).
- **Amalgam reveal video** (YouTube `xVxyknOxAt8`). **The user uploaded it.** YouTube blocks
  downloads from this environment ("sign in to confirm you're not a bot"), so don't try to get
  around it. Ask the user to re-upload it if frames are needed. Useful timestamps:
  - 10.5–12.5 s: steep top-down onto the −X cam cover, with the headers below it. Its camera is
    solved: `video_011.4s_topdown`.
  - 19–22.5 s: slow side pan along the −X headers, catalyst and alternator, low and from the
    front. Camera solved: `video_021.4s_lowfront`. That solve is unreliable because the picked
    points are nearly collinear.
  - 34–75 s: a full 360° orbit at an elevated angle. 34–44 s covers the −X side, 44–52 s the
    rear, 53–63 s the +X side, 64–75 s the front.
- **Facts from the web:**
  - The alternator is a **Denso SC7**, Ferrari part 829167, and fits the SP3, 812, 12Cilindri
    and Purosangue (Eurospares).
  - The SP3 catalyst is a **three-way catalyst + GPF in one housing** next to the block
    (FerrariChat).
  - **812 exhaust photos and parts are not valid references** for the SP3's exhaust shape. The
    812 is front-engined, so its packaging differs. Engine-mounted accessories are shared.
  - Eurospares diagrams have no images ("coming soon").
  - FerrariChat and eBay block automated requests. Don't try to get around them.
  - NOVITEC SP3 press photos (hdmotori.it) only show the engine bay from above.

## 5. Methods that work (and why)

1. **Colour segmentation:** `seg_top.py`, `measure_top.py`, `measure_side.py`,
   `measure_front.py`, `trace_cover_profile.py`. Red cam covers are separated by hue and carbon
   by low value/saturation. Measure **relative to a part at the same depth** (the cam cover),
   which cancels perspective.
2. **Camera solving:**
   - `fit_camera.py` covers photo 13. `solve_camera_constrained.py` re-solves it with a fixed
     elevation. `fit_view.py` handles any other photo, from picked coils, filler cap and cover
     flange bolts.
   - **Pitfall:** points that lie roughly in one plane give ambiguous solves. Photo 13's plain
     PnP chose a false 45° elevation. The round differential flange proves the photo is
     near-level, so it's fixed at 5°.
   - `fit_view.py` now rejects solutions with points behind the camera and enforces
     `cam_side`.
3. **Overlay and IoU** (`fit_camera.py`): renders flat-colour ID masks and compares outlines.
4. **Two-view reconstruction:** height comes from the side photo, plan position from the top
   photo. That gave the oval catalyst canister and the header depths.
5. **Tracing a photo crop** (`compare_section.py` / `render_section.py`) for like-for-like
   checks.
6. **Back-projection through the solved camera:** this is now the default for anything traced in
   photo 13. Pick pixels, then intersect each pixel's ray with a plane at the part's depth
   (`zoom_to_3d` in the build; a 10-line numpy version is in the next item). The old flat mapping
   (y = 605 − (u − 513)·0.730) is only right at the coil plane.
   ```python
   R, L, f = cam["rot"], cam["loc"]*1000, cam["lens"]/36*1800
   d = R @ [(u-900)/f, -(v-600)/f, -1];  t = (x - L[0]) / d[0];  y, z = (L + d*t)[1], (L + d*t)[2] - 150
   ```
7. **Header depth solver** (`tools/dump_headers.py` → `tools/solve_header_depth.py` → paste into
   `P["exhaust"]["tube_anchors"]`):
   - Every traced point slides only along its photo-13 ray.
   - Tubes keep a surface gap of at least 3 mm, measured on the real order-4 NURBS curve with
     per-point radius.
   - Centrelines stay inside the top-photo-20 envelope (−360 ≤ x ≤ −282).
   - `OCCLUSION` encodes which tube hides which in photo 13.
   - `INIT_HINT` gives a starting layout that already respects the stacking order. Without it
     the solver lands in local minima.
8. **Ray-cast picking** (`tools/raycast_pick.py CAMERA.json u,v` or `col=U v0 v1`): `scene.ray_cast` from the solved camera
   through a pixel tells you which part and depth the render shows there. It settled the
   tube-width question in seconds. Hide `hide_render` objects first, or the Amalgam envelope
   swallows every ray.
9. **Clash check:** `sanity.py` CLASH flags interpenetrating primaries using BVH overlap. It
   exempts both tube ends, so the collector and 2-into-1 merges are allowed.

## 6. Evidence behind the main numbers (`P` table)

- **Sourced:** bore 94, stroke 78, 65°, 6496 cc (Ferrari sheet).
- **Cam cover** (photos 13 and 20, front trace 11):
  - 7.5 coil pitches long; the front coil sits 1.8 pitches behind the cover front, the rear coil
    0.7 pitches ahead of the cover rear.
  - Cross-section about 210 mm wide and 60–70 mm thick. The head-to-cover joint is about 305 mm
    from the crank.
  - Implied rod length is about 140 mm (estimate).
  - Bore pitch of 104 mm is an estimate, but consistent across views. The whole scale rides on
    it.
- **Front accessories** (front photo 11, cover ruler): see `P["accessories"]` and
  `P["belt_route"]`.
- **Exhaust** (`P["exhaust"]`, near-bank coordinates). Everything below was re-derived through
  `ba_photo13_camera.json`:
  - **Layout:** 6 into 4 into 1. Cylinders 4 and 5 merge into a fat pipe (about 70 mm) at a
    visible weld seam, and so do cylinders 2 and 3 (about 52 mm). Cylinders 1 and 6 arrive
    separately through their flex bellows. All four pipes enter a short plenum on the V-band
    ring. Sources: photo 13 at 2–3×, video frame 20.8 s.
  - **Tubes:** each has its own traced diameter (36–46 mm). The merged sections swell through
    per-point curve radius. The old 1.35× inflation is gone.
  - **Bellows:** convolutions 60 mm OD, sleeves 44 mm OD, 7.2 mm pitch.
  - **V-band ring:** 157 mm OD, seen exactly edge-on in photo 13, centre (−330, 347, 9). Its axis
    has no x component and rises 50.3° forward and up. The T-bolt sits on the outboard rim. The
    top-photo ring arc and the T-bolt nuts agree.
  - **Catalyst:** about 170 mm tall (top z 65–75, bottom −99 to −108). Beads are at y 449, 507
    and 682. The dome has r 87, centre −13, and drops toward its tip. The outlet pipe is 56 mm.
  - **Near-bank bung:** a hex-socket plug, with no sensor fitted (photo 13). The far bank keeps
    its sensor (photo 16).
  - **The far bank is not a mirror of the near bank** (photo 16: its front primary arches up
    first). The model still mirrors it. That's a known gap.
- **Near-side details** (`P["near_side"]`): alternator sections, water pump, oil pump body, sump
  lobe and differential cover, all traced from photo 13.

## 7. Status of the focus section

- **Good and checked against several views:**
  - header layout, depths and diameters
  - clamp
  - catalyst silhouette
  - oil and water pumps
  - differential cover (bolt circle fitted to 0.2 px)
  - brace rod
  - port flanges
  - alternator
  - cam cover lip
  - belt
- **Checks:** verify, sanity (now including CLASH) and the photo 13 crop comparison all pass.
  Tube widths were confirmed by ray-casting.
- **Also matched since:** intake pods (side and top), cam cover (holes, front rise, filler,
  matte paint), coil boots and the pod sensor box.
- **Still not right (priority order):**
  1. **Far-bank headers** are mirrored from the near bank, but photo 16 shows a different route.
     The best far-bank sources:
     - photo 04: a clean +X side view, cropped at the front
     - photo 08: a close elevated front-3/4, the clearest
     - photo 16
     - video orbit frames 54–60 s: +X side views
     Photo 08 suggests the topology matches the near bank (front tube drops into a bellows,
     rear arches merge, rear bellows tube); the routing details differ. Method: trace photo 08
     or 16 through the `ba_photo16` camera (now consistent with the model), then run the depth
     solver with a photo-20 envelope for x > 0.
  2. **Front section:** photo 11's joint-solve camera is degenerate (six near-coplanar points).
     Add pulley centres, the coolant manifold hub and the pod tips, then trace the timing cover.
  3. **Gearbox case** behind the differential cover: the real one is a ribbed casting (photo 13
     u 230–400, photos 14/15/07). The model is still a box with an X-rib.
  4. **Hidden clash:** the timing chain runs through the solid head front (see section 10).
  5. **Smaller items:**
     - throttle body casting and actuator detail
     - pod side fittings
     - merge plenum (the real fat pipes flare straight into the ring)
     - carbon weave too visible
     - studio backdrop gradient
- **Front section** (started, needs its own pass):
  - `tools/fit_front.py` now rejects solutions with points behind the camera and requires the
    camera on the front side. It still lands at about 25 px of error, and the render comes out
    more elevated than photo 11. The cover-corner picks are too noisy to pin the elevation.
  - **Next:** pick better front anchors (crank pulley centre, A/C and alternator pulley
    centres, coolant Y-manifold hub, cover outer corners), solve with the elevation fixed near
    0–3° (as `solve_camera_constrained.py` does), then fit the timing-cover outline and the
    accessory positions.
  - Pulleys are now polished aluminium. Before, the crank pulley used the black DLC material.
  - **Done since:** the front casting outline is traced from photo 11 (`P["front_casting"]`,
    crank-centre origin, 0.84 mm/px), and the crank pulley radius is 72 (145 mm across, from
    the same photo).
  - **Resolved: joint solve** (`tools/bundle_adjust.py`). It covers photos 13 and 11 and video
    frame 11.4 s, with unknowns for each camera, the alternator and two global scales. Results:
    - The global scales come out at 1.006 (horizontal) and 0.994 (vertical), so the model's
      proportions are consistent across views.
    - Errors: 4.2 px (photo 11), 6.3 px (photo 13), 10.4 px (video).
    - **The real cause:** front photo 11 is not near-orthographic (the solved lens is about
      91 mm). My orthographic 0.84 mm/px reading inflated heights, so the alternator read 81 mm
      when it's actually 37 mm.
    - **Re-derived from that:** front picks back-projected with `tools/backproject.py` through
      `reference_data/cameras/ba_photo11_camera.json` give the front casting outline, the A/C at
      (167, −25), the idlers, the water pump x (−162) and the alternator at (−257, z 37).
    - Use the `ba_*` cameras from now on, and extend the joint solve with more views and features
      rather than solving views one at a time.
    - **Five-view version (current):** photos 11, 13 and 16 (mirrored), and video frames 11.4 s
      and 21.4 s, with the header landmarks as free points.
      - Absolute scale is unobservable from images, so k_h is fixed at 1 (the bore-pitch ruler).
        k_v comes out at 0.997.
      - Landmarks are in `measurements/header_landmarks_ba.json`. They agree with the model
        within about 10 mm for both bellows, the O2 sensor and the alternator.
      - The arch top comes out at −434, so the model anchor is now −415.
      - **Clamp resolved:** photo 16's clamp pick was wrong and has been removed. Without it the
        clamp solves to (−360, 331, 50), matching the model, and the worst photo 13 error drops
        from 43 to 27 px.
      - **Caveat:** k_v swings between 0.95 and 1.0 depending on the pick set, and the photo 13
        lens is poorly constrained. Add features at different depths (differential flange,
        alternator pulley, pod throttle body) before trusting k_v.
- **After this section:** the front (timing cover shape, coolant manifold, belt detail), the
  intake pods (the user said to deprioritise them earlier), the gearbox, mufflers and
  tailpipes, and the +X side.

## 8. Pitfalls already hit

- Blender "simple expression" drivers can't use `**`. Use `pow()`. Every driver must stay
  simple (verify check 1).
- Setting an object's ID properties from Python needs `obj.update_tag()` before
  `frame_set()`, or the drivers keep stale values.
- Blender's default startup cube swallows the engine. `hide_startup_cube()` handles it.
- `rm` with a relative path after a `cd` gets blocked by a safety check. Use absolute paths, or
  just overwrite files.
- Don't get around bot checks or hotlink protection (YouTube, FerrariChat, eBay, the hdmotori
  CDN). Original-upload URLs and plain requests are fine.
- **Photo 13's lens is unobservable** from the current picks: the cost changes by 3% between 35
  and 200 mm. An unconstrained solve chose 35 mm and tipped the camera to look up. That
  inflated near parts by about 10% and drove a false "+15 mm" catalyst correction and a
  1.35× tube scale. It is now pinned at 100 mm (studio macro). A look-down prior of 3.5°
  comes from the stand-cup ellipses: their rim ratio is 0.13–0.19.
- **Don't mirror photo 16 for near-bank tubes.** The banks are routed differently. Mirroring is
  fine for the catalyst, clamp and bellows positions, but it gave a wrong −415 arch anchor.
- **Brightness profiles across polished tubes lie:** reflections make dark bands inside the
  silhouette. Ray-cast or look at the image instead.
- Verify checks: mechanism errors under 0.01 mm, valve-to-piston clearance above 0
  (currently 1.06 mm), piston skirt to counterweight above 0 (3.0 mm).

## 9. Git

- Work goes on branch `claude/magical-bell-4e0g8c`. Commit and push after each meaningful step.
- Commit messages end with the attribution lines given in the session's system reminder.

## 10. Recent changes (newest first)

- **Cam cover:**
  - Walls are now ~8 mm thick. The old 1.7 mm walls plus the edge bevel left holes: the cam
    towers showed through as a dark "seam", and the timing chain showed at the front.
  - The lip step is softened.
  - 14 mm cam-drive rise at the front (`P["cover_bulge"]`, module helper `cover_bulge()`), with a
    deeper pocket under it.
  - Figure-8 filler with a chrome surround and a handle tab.
  - Matte crinkle red (no clear coat).
  - Pod side: black sensor box with connector, and coil boots resized.
  - **Known internal clash:** the timing chain's outer run (y ≈ −30) passes through the solid
    head front and the cover's lip and side walls. It isn't visible. The real head is hollowed
    for the cam drive.

- **Intake pods rebuilt.**
  - Side profile traced in photo 13 through the solved camera: flange z 374, crest about 186 mm
    above it, nose at y −30.
  - Cross-section: a flat plenum lid at 100 mm, plus a horn duct whose crest moves from 0.80 to
    0.50 across the pod. The outer side has a shoulder, a bulge at 40% of the height, and an
    undercut back to the flange.
  - Lid bolts, chrome "Ferrari" script (outboard-up, as in photo 20), and flange bolts on a cast
    ledge. Spine half-width 9 mm.
  - Glossy-coat carbon.
  - `reference_data/cameras/photo20_top_approx_camera.json` is an approximate top camera built
    from the photo 20 cover-ruler mapping (not a solve), used for top-view checks.

- **Joint solve fixed at k_v = 1.** With k_v free, the saved cameras only fit a model squashed
  6.6% vertically, so photo 16's coils rendered 50–70 px off. With k_v = 1 every `ba_*` camera
  matches the model as built (photo 16 now overlays well). The photo 13 camera moved down about
  20 px, so every photo-13-derived lower part was re-mapped (old pixel → new ray at the same
  depth): z +15 for the clamp and catalyst, +16 for the pumps, sump bosses, alternator,
  differential cover, hairpin, bracket, gusset and gearbox case. Tube depths were re-solved.
  - **Caveat:** whether the cover sits about 15 mm too high relative to the lower parts, or the
    other way round, is within noise (k_v 0.93–0.98 when free). Treat the absolute z of the
    lower parts as ±15 mm.
  - **Photo 11's camera is degenerate:** six near-coplanar front points give a 185 mm lens at
    about 22° elevation. Add non-coplanar front features before using it.

- Catalyst re-traced through the solved camera (170 mm tall, outlet 56 mm, beads moved). The
  oil pump, water pump, differential cover and brace rod were rebuilt from back-projected
  photo-13 outlines.
- Near-bank headers rebuilt (6 into 4 into 1, depth solver, traced diameters, 157 mm edge-on
  V-band). Added the CLASH check: the old geometry had 8 interpenetrating tube pairs.
- Joint solve: photo 13 lens pinned at 100 mm with a look-down prior. Cameras re-saved. The
  joint solve takes `F140_FIX_LENS` to override the pin.

- Carbon is now near-black with a clear coat (base roughness 0.22). The mufflers are satin
  polished.
- Black bracket at the rear of the near-bank head (`NS["rear_bracket"]`).
- Exhaust polish roughness raised to 0.19. photo_studio_01 is the default HDRI.
- Oil pump and water pump rebuilt from a 2× zoom of photo 13.
- 1.5 mm angle-limited bevels on all castings. Bolts that sat in a cam cover end wall were
  removed.
- Five-view joint solve (`tools/bundle_adjust.py`). The bad photo 16 clamp pick was removed.
  Arch anchor −415, O2 sensor angle 22°.
- Front geometry re-derived through the jointly solved front camera
  (`tools/backproject.py`).
