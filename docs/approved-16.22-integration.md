# Approved 16.22 integration candidate (not activated)

REUSE: existing 16.22 API/bridge/permission/voice implementations and synthetic browser rigs.
EXTEND: retain the live recents-first Share targets and Send to chooser, with its original regression suite.
NEW: executable live-feature map and explicit app-parity rename evidence. No parallel implementation.

Source parents: actual served 4566306576d3a6805da1ba531da3a89214dfd7af; offered runtime 6ab2ed06c48787acb22828b6296597f6f1dfe1a7 (the offered store recipe is separately dadb160). Packaging conflicts use the offered runtime's version/config/server/compose definitions; its deleted connectors.compose.yml is superseded by the consolidated docker-compose.yml, not silently kept as a second dispatcher. Inspect the consolidated connector services during worker acceptance.

Runtime delta from offered runtime: only static/unified.js, the recents-first code already live plus synchronous list-scroll retention on row refresh. Other additions are docs/tests and Dockerfile.approved-integration. The offered recipe dadb160 is merged intact, retaining its immutable Messenger/Telegram pins. Those pins still identify the UNMODIFIED offered image; an isolated candidate must explicitly override MESSENGER_IMAGE to the newly packaged integration image. This is a source candidate, NOT the published 16.22 image. Dockerfile.approved-integration copies only unified.js over the digest-pinned 16.22 image after worker custody checks; never use the legacy Dockerfile.overlay 15.12 carrier. Do not overwrite an existing version/tag or edit live recipe pins.

## Feature mapping (no waivers)
- All and Unread survive as SEGMENTS; Direct/Groups/Merged survive in Filters → Type. The literal-array refactor hid them from the text inventory. Candidate tests evaluate the actual arrays and verify their rendering call sites. Browser tests must still demonstrate clicks.
- Move to Inbox / Move to Low priority become Priority → Normal / Low. setPriority executes the same low_priority change, adds Medium, paints before awaiting, and rolls back a failed request. Original success messages survive conditional assembly; failure text is now Could not change priority. New VM tests execute the source function, not a reimplementation.
- Test Person was a test fixture label; the original retained share-recents suite supplies it again. No contact or owner data was copied.
- Recents-first Send to / shared targets (including groups, deterministic ties, twelve-row cap, no alphabet headings) are retained; ordinary New chat stays A–Z. Existing four Node tests exercise these cases.

## Acceptance still required
- Exact-source worker baseline/candidate Python and Node suites, plus all affected browser rigs: filters/layout, inbox UX/tweaks, desktop split/divider send, voice capture/original/recovery, pickers, incoming/react media, agents and drafts. Distinguish inherited failures; none is a waiver.
- Isolated synthetic shell/app via canonical wizard-stage, no live upstream or owner credentials. Stage the changed Inbox/Filters/Priority menus, composer, Send to, draft-only share and voice-recovery flows. Block non-loopback browser traffic and all owner-origin mutations. Fake providers are seam proof only.
- Appearance v1 --wz-* roles; inspect in-shell phone/desktop screenshots in obsidian and obsidian-light, switch skin live without remounting, and dark standalone fallback. Text-bearing floating menus must be fully opaque; Back and outside click close them without exiting. Deny sends outside synthetic fixture APIs.
- No live activation, WAM change, update-mode change, source-pin selection or owner-account unlock is authorized by this document.

## Source/browser repair (worker verification pending)
REUSE: unchanged 16.22 runtime carrier, app-parity inventory, existing strict desktop scroll assertions and ten browser rigs.
EXTEND: drawList row replacement restores the scroll offset synchronously; the browser still clamps naturally when a filter shortens the list. No delayed restoration may override a later scroll gesture. A focused VM regression checks this write order, not a browser result.
NEW: common synthetic scroll fixture for baseline/offered/pre-fix/fixed static assets, on desktop/phone in two skins. This comparison must locate inherited vs offered behavior before the repair is accepted. The original full desktop harness retains every assertion, captures failure state, and always closes Chromium; a deliberate post-launch exception tests teardown. Optional layout-reading trace instrumentation is diagnostic-only and is not enabled for the fixed candidate acceptance run.

The prior worker failed before Python collection (missing isolated_sender dependencies), parity provenance (archive directory incorrectly initialized as an unborn Git checkout), and desktop scroll preservation. Its nine other browser logs contain real interaction success markers, not skip-only exits. They are historical proof only: changing unified.js requires rerunning all ten against the new candidate. The worker must install the repository's pinned isolated_sender requirements, verify actual commit/tree archive custody, and keep extracted archives outside any Git worktree. Do not invent commits or remote refs for the parity gate.
