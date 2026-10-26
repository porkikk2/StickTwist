# StickTwist

**Production update:** paper-cutout style 5 is approved. Voice option 1 (am_michael) and the Spend $100m in one day premise are owner-selected. Narrated script drafts for Shorts and a 5–8-minute widescreen story are in preparation; music and publication remain unapproved. See [new direction](editorial/DIRECTION.uk.md). Legacy scheduled rendering is paused unless `LEGACY_RENDER_ENABLED=true`. The full paper-style renderer for both formats is not integrated yet; the approved visual proof is the eight-second motion test.

Original English fictional stories, animated with procedural 2D stickmen. Cloud-only rendering, a five-story weekly queue, and explicit owner approval before every YouTube upload.

**Channel:** StickTwist · preferred handle `@StickTwist` (availability not verified).  
**Description:** Original stickman stories. Unexpected twists. All stories are fictional.

## Operating costs: £0

- Only standard `ubuntu-24.04` GitHub-hosted runners in this **public** repository. All jobs skip private repositories. No self-hosted runners, larger runners, GPU services, Codespaces, or paid inference.
- No Actions artifact uploads, dependency caches, Git LFS, cloud billing accounts or paid API keys. Review bundles are software test outputs attached to **unpublished draft releases**, visible to users with push access.
- Piper neural TTS runs on the cloud runner using `en_US-ljspeech-medium`; its dataset is public domain. No remote speech API, voice cloning or audio subscription.
- Scripts come from an offline deterministic story grammar plus five authored launch stories. This is not an LLM. The launch bank contains 29 distinct scripts; many later scripts share a structure. Owner editorial review is mandatory. After five complete weekly batches the remaining four are held; generation stops until more original stories are added. It never quietly recycles scripts.
- Provider limits/terms can change. Stop workflows if free service ceases; never enable a paid fallback. No GitHub billing settings are modified by this project.

## Weekly operation — legacy prototype, currently paused

Actions → **Build review videos** runs Sundays at 06:15 UTC. It prepares the coming Monday's queue and renders five videos sequentially. GitHub schedules may be delayed and can be disabled after prolonged repository inactivity. Manual dispatch is available.

The five suggested release slots are Monday–Friday at **17:00 Europe/London**, with daylight saving handled in Python. These are editorial suggestions: **no scheduled or automatic YouTube publishing exists**. A missed approval never counts as consent.

To make only the first test, run Build review videos with week `2026-10-26`, count `1`. The queue still contains five scripts. Re-running the same week reuses the same queue; each render run produces a separate preview draft.

## Review and approve

1. Open the completed run's summary → **Open unpublished draft**, or open [Releases](https://github.com/porkikk2/StickTwist/releases).
2. Keep the release a **DRAFT**. Download an episode ZIP and inspect `video.mp4`, `review.jpg`, `captions.srt`, `story.json`, `metadata.json` and `manifest.json`.
3. Check the complete story, naturalness of narration, caption timing, safe screen margins, and YouTube title/description. Captions are phrase timing estimates within separately synthesized beats, not forced word alignment.
4. Only when satisfied, use Actions → **Approve YouTube upload**. Enter the preview tag, episode id, exact ZIP SHA256 and your intended visibility. Confirmation must be exactly `APPROVE <episode_id> <bundle_sha256> <visibility>`.
5. Only the repository owner's manual dispatch on `main` passes. Uploading is initially disabled and also requires OAuth secrets; see [YouTube setup](docs/YOUTUBE_SETUP.md).

A SHA256 approval binds the **whole bundle**, including the MP4 and metadata. Altered bundles fail. Even a private YouTube upload needs your approval. Visibility defaults to private. Public visibility requires explicit `public` approval. There is no automatic promotion from private to public.

The uploader checks the intended channel and creates an upload claim in an unpublished ledger **before** contacting the upload endpoint. A completed or interrupted attempt blocks automatic retries for that episode. On failure, inspect YouTube Studio first; remove a pending claim only after verifying no video exists. This deliberately favors avoiding duplicates over blind recovery. Never publish the ledger draft.

## Media output

1080×1920, 9:16, H.264/yuv420p, 24 fps, AAC audio, loudness normalization, fast-start MP4, burned-in English phrase captions and companion SRT. Seven scenes include gestures, facial expressions, moving objects, progress indicator and recurring character colors. No stock footage, copyrighted clips, background songs or logos are used.

Every render checks the actual video/audio streams and duration with FFprobe. The pipeline rejects excessive narration rather than cutting off the ending. Story and caption checks run before media processing. `review.jpg` is a cloud-generated seven-scene contact sheet.

## Development without local video processing

```text
python -m unittest discover -s tests -v
python -m compileall -q sticktwist
```

These checks handle text and small synthetic integrity fixtures only; they do not render video or synthesize speech. The renderer rejects local and self-hosted environments. Install full media requirements only in GitHub Actions. Rendering code checks the cloud guard before importing Pillow/Piper.

See [launch scripts](stories/launch.json), [source notes](docs/SOURCES.md), and [YouTube setup](docs/YOUTUBE_SETUP.md). No credentials belong in source control, issues, logs or chat.

