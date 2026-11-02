# Measuring shape from photos

These scripts turn reference photos into numbers the build script can use, then score the
model against the photo.

1. **Segment by colour.** `seg_top.py`, `measure_top.py`, `measure_side.py` and
   `measure_front.py` pick out the red cam covers (hue) and the black carbon (low value and
   saturation). They trace outlines and measure edges column by column. Every dimension is
   expressed as a ratio to a reference part at the same depth (the cam cover), which cancels
   most perspective error.
2. **Solve the camera.** `find_coils.py` locates features that can be matched exactly on the
   model (the six coil boots). `fit_camera.py` solves the photo's camera pose with OpenCV
   `solvePnP`, sweeping or fixing the lens. The leftover reprojection error at each point
   shows which model dimensions are wrong.
3. **Score and overlay.** `fit_camera.py` renders flat ID masks (covers red, carbon green)
   from the solved camera. It draws real (green) and model (magenta) outlines on the photo
   and reports IoU per part.
4. **Fit.** `fit_pod.py` iterates on one part: compare edges, convert pixels to millimetres
   using a known ruler, update the parameter table, rebuild, repeat.

Run the segmentation tools with any Python that has `opencv-python-headless` and `numpy`.
Run the camera, fit and render tools with Python plus the `bpy` module (or `blender -b -P`).

Known limit: a single side view can't pin the camera's elevation when most matched features
sit at one depth. Use views where the dimension you're fitting doesn't depend on depth, or
fit several views together.
