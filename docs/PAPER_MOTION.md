# Style 5 — short movement test

The owner selected paper cutout after rejecting the original neon stickman presentation. This is a silent eight-second visual study, not a completed video or a publishing approval.

Assets were generated from the selected concept using built-in image generation: an empty room plate and a transparent 16-part puppet atlas. Prompts requested matte cardstock texture, white round heads, black paper-strip limbs, turquoise/orange shirts, expressive faces and separate console/cash pieces. No outside paid API is configured. The atlas is segmented, cleaned and assembled only on the cloud runner.

Paper cutout motion test is manual-only. It runs on a standard public-repository ubuntu-24.04 hosted runner, without caches or Actions artifacts. The renderer checks the cloud-only guard before importing image libraries or processing assets. Output stays in an unpublished release draft.

Movement study: entrance/walk, discovery, raised arms and face change, guilty friend reaction, close-ups, final speech bubble. Two-bone joints and separate head/hand/prop layers move independently. This is not an image-to-video diffusion model; it is a reusable 2D paper puppet rig animated in Python and encoded with FFmpeg.

No voice/audio in this test. No YouTube operation. Background and parts are project concept assets; the original concept image is not used as a flat moving character layer. Review the actual MP4 for timing and motion quality; passing rig or codec tests does not establish creative quality.

Visual QA found that the original room foreground made the puppets appear to stand on furniture. A revised plate, room-clear.png, removes the foreground bed/chair/desk to create an unobstructed floor. The rejected first cloud render is retained under work/, not delivered as the chosen result. The puppet rig is unchanged; a fresh cloud run uses the corrected plate.
