# Combined QA continuation (test/release tooling only)

Production `static/connectors.js`, `static/unified.js`, and `static/unified.css` remain byte-identical to 9469e8414db1958e1b5140b77bda6f5cace1d4d4.

## Finite fixture closure

All 13 suites discovered by the existing runner were audited once, including non-`test_` suites. `test_connector_login_runtime.cjs` runs connector cancellation, credential/poll, QR/PIN, challenge, and Telegram setup branches: it needs a real className-backed classList and descendant class/tag lookup. Its seven original regression assertions remain unchanged. Telegram's fixture now explicitly selects its dormant Add tile before opening setup (both first and refresh paths); automatic setup cards must not be restored to satisfy a test.

`test_connectors_view.cjs` already provides the add/remove cancellation contract and explicitly selects Add; no browser-flow ResizeObserver/event geometry calls are reached by either VM suite. The shared VM helper already supplies URL/history, storage/events, document and classList for `test_agent_permissions_view`, `test_history_search_view`, and its own contract suite. The former retains the exact five case-level baseline-identical failures; these must never become green by weakening assertions. `test_draft_attachment_recovery` remains unchanged. `test_view` owns an independent app.js DOM; push-settings has an explicit environment; unified-view uses exported pure Back state. Reactions, share-recents and voice-speed use source slices; trusted-owner-gateway uses its existing gateway fixture. No global-by-global trial loop or new test portfolio is introduced.

The two account browser scripts execute real Chromium DOM, not this VM. Existing merged account acceptance retains exact Add → Add an account routing, actual hosted Nebula/Sepia paint switches, decoded-pixel opacity and injected-transparent negative, constrained fit/full-size mapping, back/outside close and standalone dark fallback. Attachment browser and single-send follow on the disposable synthetic ViewServer. No provider page or owner state is allowed.

## Dependencies and packaging

Forum's system Python has neither cryptography nor pytest. Selected Python closure is `test_server_drafts`, `test_agent_send` (imports `test_web`/`test_agent_keys`), `test_photo_albums`, `test_web` (test_passkey Phone is stdlib-only), and synthetic `agent_drafts_stage`. Runtime `trusted_owner` can import AESGCM. Provision cryptography 46.0.3, cffi 2.0.0 and pycparser 2.23 as real PyPI hash-pinned wheels in a new task-local directory; none of the selected modules imports pytest. Signal's environment is independent and is not awaited or modified.

The prior full Config comparison could reject classic Docker's empty serialization defaults. Reuse the observed SOURCE_DEFAULTS contract from `/srv/work/messenger-worker-identity-3a35ed04b9bb-indexfix-v1/worker_identity.py`: first require exact verified archive manifest/config ID; permit only enumerated empty fields absent from raw Config. Preserve every raw field and ordered layer and platform check, reject unknown/nonempty expansions, and retain changed `/app` file and one-layer overlay assertions. Existing packet guard case covers positive and negative expansion in place. No label/rootfs-only identity acceptance.

The original failed stage/evidence is immutable and retained. Cheap fixtures may rerun in a fresh stage; original 17-pass controller evidence, strict negatives and exact historical comparison are not deleted or relabeled. Only the parent admits this ready light job and activates through the existing guarded lifecycle; no live writes occur here.
