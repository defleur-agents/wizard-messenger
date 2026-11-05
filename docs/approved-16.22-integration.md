# Approved 16.22 integration candidate (not activated)

REUSE: existing 16.22 API/bridge/permission/voice implementations and synthetic browser rigs.
EXTEND: retain the live recents-first Share targets and Send to chooser, with its original regression suite.
NEW: executable live-feature map and explicit app-parity rename evidence. No parallel implementation.

Source parents: actual served 4566306576d3a6805da1ba531da3a89214dfd7af; offered runtime 6ab2ed06c48787acb22828b6296597f6f1dfe1a7 (the offered store recipe is separately dadb160). Packaging conflicts use the offered runtime's version/config/server/compose definitions; its deleted connectors.compose.yml is superseded by the consolidated docker-compose.yml, not silently kept as a second dispatcher. Inspect the consolidated connector services during worker acceptance.

Runtime delta from offered runtime: only static/unified.js, the recents-first code already live. Other added files are docs/tests. This is a source candidate, NOT the published 16.22 image: build/package the exact integration SHA before a deployable candidate can be claimed. Do not overwrite an existing version/tag or edit live recipe pins.

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
