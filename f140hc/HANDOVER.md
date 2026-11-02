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
export F140_REFS=$PWD/f140_work/refs F140_HDRI=$PWD/f140_work/refs/hdri/studio_small_08_2k.hdr
f140_work/bpyenv/bin/python -I f140hc/verify.py       # must print PASS
f140_work/bpyenv/bin/python -I f140hc/tools/sanity.py # must print SANITY: PASS
```

Section comparison: render the model through the solved photo-13 camera and stack it under the
photo crop.

```bash
f140_work/bpyenv/bin/python -I f140hc/tools/render_section.py f140hc/reference_data/cameras/photo13_side_camera.json out.png 596 1196 48
python3 f140hc/tools/compare_section.py $F140_REFS/amalgam/13.jpg out.png 596 1196 cmp.jpg
```

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
- **Exhaust** (`P["exhaust"]`, near-bank coordinates):
  - Catalyst: dome length 150 mm, r 97, seam at y = 449; the canister is an oval at 0.74 of its
    height in plan (top photo 20).
  - Clamp: on the dome's upper-front face, axis forward/up/outboard (`neck_out` 0.62).
  - Header tubes: traced in the photo-13 zoom (origin u = 560, v = 560, scale 2). Depth follows
    the port → collector sweep (`port_x`, `sweep_x`, `loop_bulge`, `loop_tilt`).
  - Mufflers: rear photos.
- **Near-side details** (`P["near_side"]`): alternator sections, water pump, oil pump body, sump
  lobe and differential cover, all traced from photo 13.

## 7. Status of the focus section

- **Catalyst height:** raised 15 mm after a re-check against side photo 13. Its top now
  matches within about 2 px.
- **Good, and agreeing across views:**
  - catalyst shape (dome, waist, oval canister, seams, oxygen sensor on the outboard shoulder,
    slip joint)
  - outlet pipe
  - alternator position and appearance
  - differential cover
  - lower castings placement
  - cam cover lip and bolts
  - belt routing
  - verify and sanity both PASS
- **Not yet right (in priority order):**
  1. **Header loops.**
     - From photo 16 and the top-down video frame, the real primaries are long S-bends leaving
       six separate ports, with lower loop parts that don't bulge far beyond the cover edge.
     - **Partly done:** `tools/triangulate.py` plus `reference_data/picks_headers.json`
       triangulated the clamp at (−366, 327, 59), the rear bellows at x −331 and the front
       bellows at x −307. The O2 sensor came out within 15 mm of the model. The clamp is now
       fixed at its triangulated position, and tube depths follow per-tube anchors
       (`P["exhaust"]["tube_anchors"]`).
     - **Still to do:** loop shapes in photo 16 read rounder than the real S-bends. Add more
       triangulated landmarks along each loop (arch tops, loop bottoms, port flanges) to
       `picks_headers.json` and turn them into anchors.
     - **Fix: triangulate.** Pick the same landmarks (bellows centres, arch tops, loop bottoms,
       port flanges) in photo 13, video 11.4 s and photo 16 (mirrored), using the solved
       cameras. Triangulate them and run each tube through its 3D points.
     - Real topology:
       - The front three cylinders merge low, then a pipe with bellows rises into the clamp
         from below-front.
       - The rear three merge behind, then a pipe with bellows runs forward, arches up and
         drops into the clamp from above-rear.
  2. **Block, head side and lower crankcase detail** behind the headers.
     - **Partly done:** the outboard barrel face now has vertical ribs, a head-joint rail,
       water bosses and head-bolt bosses (`F140HC_BlockSideDetail_*`).
     - **Still to do:** the black bracket near the bellhousing, oil lines and fittings, and
       exhaust port flange detail.
  3. **Oil and water pump castings:** currently simplified boxes and cylinders. Use photos 13,
     17 and 08 plus video frames 19–22 s.
  4. **Gearbox:** a box with an X-lattice of stiffening ribs and the differential cover.
     **Still to do:** the real case shape from photos 14, 15, 07, 12 and 20 (stepped
     housings, finned coolers at the rear sides, hydraulic unit, shift actuator).
  5. **Materials:** cast textures exist; the polished steel is roughness 0.15. Compare under
     both a dark and a light HDRI, since the video was shot on black.
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
      - **Clamp disagrees:** z 15 against 55 from the side photo. Recheck the clamp picks in
        photo 16 and video 11.4 s. Photo 13 errors reach 42 px with five views, so one of the
        added picks is probably wrong.
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
- Verify checks: mechanism errors under 0.01 mm, valve-to-piston clearance above 0
  (currently 1.06 mm), piston skirt to counterweight above 0 (3.0 mm).

## 9. Git

- Work goes on branch `claude/magical-bell-4e0g8c`. Commit and push after each meaningful step.
- Commit messages end with the attribution lines given in the session's system reminder.
