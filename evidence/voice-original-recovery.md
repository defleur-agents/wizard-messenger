# Owner-only original voice recovery — 16.13 candidate

This is diagnostic custody and raw export, **not a fix or diagnosis of the Mac recording failure**.

## Reuse
- capture and pending recovery: REUSE `WizardApp.capture.start / pending / ack`.
- raw-file export: REUSE `WizardApp.share.text / file` (the `file` method).
- update safety: REUSE `WizardApp.update.hold` through existing send/capture flow.
- owner upload/readback: existing ViewHandler owner session, Origin, CSRF, trusted ingress and `_raw_body` 25 MiB reader. App-owned bounded custody storage; no new public/tool authority.

## Executed on Linux Oscar, isolated synthetic data

- `CORE_DIR=<downloaded-live-core> NODE_PATH=<playwright-node_modules> node tests/voice_original_browser.cjs`
  - Actual shared capture, fake-device microphone, real-time **120005 ms** WebM, **1,925,838 bytes**.
  - Before reload, after shared pending recovery, and authenticated server readback SHA256 all **42f915a3792187cc774f11b6850b9ebed51bc47aa982de8043a85f7c69e23980**.
  - Exact production composer displays Unsent voice note / Save recording after reload in this fixture; no auto-send.
  - Unsupported raw bytes `00ff80010001020304` archived unchanged.
  - Queue archive PUT failure/readback mismatch stop before upload/send/ack; original failed job and save callback remain.
  - Export traverses actual shared SDK `share.file`; injected platform cancel/unsupported/shared outcomes stay honest and preserve raw bytes and MIME.
- `PYTHONPATH=.:tests python3 -m unittest test_voice_archive test_web test_owner_ingress`: **52 passed**.
  - Archive HTTP test runs on TCP and OwnerUnixServer; missing auth/CSRF and bearers refused, owner-only readback, traversal rejected.
  - Exact25MiB and oversized input, quota, symlink root/entry confinement,0600/0700, corruption, interrupted manifest publication and exact-budget retry exercised.
- `node tests/voice_capture_guard_browser.cjs`: all pass.
- Full Python discovery: candidate372/base370 before the added storage test, both same2 failures (stale Rust Dockerfile literal and search fixture missing crypto),2 import errors (pytest unavailable),3 skips. No new failure set.
- `wam check`: same inherited system-function findings as base (existing media playback, push SW, Messenger chat markup and old test-fixture sources). Not claimed green.
- Independent read-only Codex review found symlink confinement and interrupted-commit quota issues; both corrected, regression-tested, re-reviewed. Final reviewed range verdict: blocker resolved.

Shared resources tested:
- app-capture.js SHA256 `1c38b024e5d99f0a1331da8d84249ec922ffcdce0cbe823fdcce9a151ff6f095`
- app-client.js SHA256 `f328faec4a3c13cc61812b1a355194870743a454f1405d77d7bd282270c1dbbb`

## Existing open take / release gate

An already-loaded16.12 bubble cannot gain this hook on Retry. Server deployment does not alter that closure. Reload removes its in-memory bubble; shared pending custody is proven above in Chromium, **not on the owner's Mac and not for his particular take**. Do not direct a reload/reopen or discard of his existing take. No supported remote extraction capability was found; no device access was attempted.

New-code Send/Retry archives before conversion; Save recording shares only and never sends. Existing old-code Retry cannot archive. Preserve the old open bubble until custody can be established by an owner-side supported action. Do not auto-send to James.

At the deployment preflight owner activity was5 seconds old, outside quiet hours: gated lifecycle must wait, no override. This document is candidate test evidence, not Store publication, production deployment or recovered-owner-take proof. Store digest pin, publish, gated update, exact live assets/bridge health/ingress/smoke remain release gates.
