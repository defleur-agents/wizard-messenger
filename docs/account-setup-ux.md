# Account setup repair — 5 November

## Scope and provenance

Candidate starts at exact live Messenger revision `4566306576d3a6805da1ba531da3a89214dfd7af`, image `sha256:75dde49255cdb88b789103170b69c68517a7acc6a8523fec3ee0f2174235b84e`. Static hashes and `browser_signin.py` were compared with the serving container; there was no runtime source diff. No provider page, owner session, login form or CAPTCHA was inspected. The unrelated dirty original checkout is untouched.

History (`ca4123c` and current `show()`) establishes the existing placement: Add is the plus tile after Your accounts, with an Add an account grid. Worker readiness incorrectly promoted disconnected providers out of that grid into full Settings cards. Warm Slack and Instagram now stay in Add. Existing accounts retain their management tiles, including degraded accounts with retained logins. Selecting a network opens only its own card; no account rendering starts a browser.

## Component inventory: REUSE / EXTEND

Read Wizard `docs/COMPONENTS.md`, including skin/Appearance and existing links. REUSE Messenger's `MessengerConnectors`, `plusTile`, `tile`, `card`, `manage`, existing `u-overlay`/`u-sheet`, owner-only disposable `/connectors/browser/*` flow, cleanup/generation fence, shared Appearance client and host. EXTEND only viewer geometry, Fit window / Full size controls, pan/scroll controls and connector one-layer Back. NEW browser/provider/capability: none. Authentication, isolation and cleanup backend are unchanged.

## Acceptance

`tests/account_setup_browser.cjs` uses intercepted synthetic API data and a generated 1280×1000 framebuffer with marked corners. It blocks all nonfixture origins. It exercises the full app in a hosted proxy using pinned real `skins.js`, `appearance-host.js`, `app-client.js` and palette CSS, not invented theme colours. Profiles: phone 360×640 with enlarged text and touch/mobile UA; constrained desktop 860×620; desktop 1280×860. It tests Add placement for warm providers, only selected setup, no automatic browser start, fit bounds and controls, full-size panning and normalized tap mapping, page scroll/navigation, session cleanup and one-layer Back/outside dismissal, skin changes without document/session replacement and pixel-identical opaque panel over loud content. Screenshots must be visually inspected after the queued run; this proxy is not physical-device or real-login proof.

`tests/test_connectors_view.cjs` and `tests/new_connectors_browser.cjs` retain existing QR/credential safety and tile-management coverage with the corrected selection step. No actual credentials are used.

## Release contract (parent only)

Run `python3 tools/run_account_setup_qa.py` on forum through the durable queue. It produces logs, screenshots, summary and a narrow static overlay payload with hash manifest. This task does not deploy. Rebase/cherry-pick the three static changes onto the parent's current composite release before activation; do not overwrite attachment/Signal work. `release/account-setup.Dockerfile` requires an explicit immutable BASE supplied by the release owner and copies only those three static files; all existing features and backend bytes remain from BASE. Run app parity against the exact activation composite.

Preserve both owner Runtipi worker overrides (`slack`, `instagram`), their loaded immutable image IDs and `pull_policy: never`. No broad restart; no child activation. Parent must serialize activation and read back exact static hashes plus the two worker overrides and original service identities. Provider login remains owner-only; no CAPTCHA solving or credential inspection is part of this repair.
