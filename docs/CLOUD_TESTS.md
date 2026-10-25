# Cloud validation — 25 October 2026

Source revision tested: `662202c2150ac13be1662798477cd724173fc4cf`.

15 unit/integrity tests passed locally without media processing, then passed on GitHub Actions. All five launch stories rendered and passed real FFprobe checks in the cloud.

[Successful full run](https://github.com/porkikk2/StickTwist/actions/runs/40198549171): 2 minutes 18 seconds.

| Episode | Duration |
|---|---|
| My Best Friend Sold My PS5 | 40.83 s |
| My Roommate Charged Me for My Own WiFi | 42.96 s |
| My Brother Sold My Concert Ticket | 41.54 s |
| My Neighbor Returned an Empty Box | 42.17 s |
| My Friend Faked a Surprise Party | 45.17 s |

Review-only bundles are stored in an unpublished release draft accessible to push-access users. No YouTube upload was performed. YouTube OAuth/channel authorization is not yet configured; the API upload path has integrity/approval unit coverage but has not been tested against a real authorized channel. Uploading remains disabled.

The first standalone PS5 test was also successful: [run](https://github.com/porkikk2/StickTwist/actions/runs/40197261591), 40.375 seconds. Its downloaded ZIP and every asset hash were verified, and its seven-scene contact sheet was visually inspected. Speech naturalness and phrase-caption synchronization still require owner playback review before approval.
