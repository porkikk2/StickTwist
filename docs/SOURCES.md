# Sources and third-party components

Verified 25 October 2026. Provider documents may change.

- GitHub standard public-repository runners are free: https://docs.github.com/en/actions/concepts/billing-and-usage
- Artifact/cache storage has separate metering; this project uses neither: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Release limits: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- Only push-access users see draft release listings: https://docs.github.com/en/rest/releases/releases
- Piper Python API: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md
- Piper CLI/download: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md
- Piper engine is GPL-3.0; installed from PyPI on the runner, not vendored here: https://github.com/OHF-Voice/piper1-gpl
- LJ Speech medium voice model card, public-domain dataset: https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/ljspeech/medium/MODEL_CARD
- Voice repository/model licensing: https://huggingface.co/rhasspy/piper-voices
- FFmpeg licensing depends on build configuration: https://ffmpeg.org/legal.html
- Google Desktop OAuth: https://developers.google.com/identity/protocols/oauth2/native-app
- OAuth testing-token expiry: https://developers.google.com/identity/protocols/oauth2#expiration
- YouTube videos.insert: https://developers.google.com/youtube/v3/docs/videos/insert
- API project upload restrictions: https://developers.google.com/youtube/v3/revision_history

All visual geometry and launch scripts were created for this project. No claim that generated stories have never coincidentally resembled any existing work. The PS5 reference is fictional narrative use; no PlayStation artwork, logo, game footage or affiliation is included. Voice licensing and engine licensing are distinct. Keep dependency licenses if redistributing dependencies. No third-party soundtrack is included.

## New voice auditions and sound design

Kokoro-82M model/weights: Apache-2.0, downloaded into the ephemeral standard cloud CPU runner only; no paid inference endpoint. Model card: https://huggingface.co/hexgrad/Kokoro-82M . Voice catalog: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md . Library: https://github.com/hexgrad/kokoro . Audition candidates am_michael, bm_george, af_heart are not yet owner-approved production voices.

Demo music is generated from procedural note sequences in sticktwist/audio_auditions.py. Demo effects are synthesized noise/tone envelopes. No sampled song or outside sound-effect recording is embedded. Keep the audio manifest as provenance. No claim of guaranteed immunity from automated platform matching systems.
