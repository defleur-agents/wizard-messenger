# Signal QA VM fixture repair (test-only)

Production baseline: `e2ba054c4d12d8943243af30c6978d4b99f112b3`.

## Root cause and scope

Both inherited domain fixtures evaluate **all** of `static/unified.js` but only supplied a historical subset of its browser environment. VM contexts do not inherit Node host globals. Adding WebCrypto alone left immediate `takeChatLink()` reading an undefined `location`; mount would next need interval timers and connected DOM, and asynchronous list/titlebar paths need selectors, attributes, storage and fragments. `tests/fixtures/unified_browser_inventory.json` records the complete top-level/bootstrap and mounted-path audit. This is not a product defect and no product guards are added.

`helpers/unified_browser_context.cjs` provides explicit URL-backed same-origin location/history, real WebCrypto/URL/query/abort/text primitives, string storage, registered events, controlled timers, class/style/attribute state, connected synthetic DOM and moving fragments. Unsupported selectors throw; unknown APIs are not invented. Callback errors propagate. Optional shell/observer/media capabilities remain absent; accidental fetch/media playback throws. Existing fixtures retain their lowercase tagName convention and synchronous rAF override; they are not browser/layout proofs.

New contract tests load the entire shipping IIFE, check dependency inventory drift, valid/invalid chat hashes, path/query preservation, replaceState's structured-clone/no-event semantics, storage, DOM/event/timer state, and mount/authentication/resize/pagehide/signout at phone and desktop widths. The runner executes this contract before existing suites and writes a separate unit checkpoint before any pinned Go/Rust build. `--unit-only` uses `evidence-preflight/`; normal continuation uses `evidence/`. Exactly the pre-existing converter-optional skip is allowed before building; actual converter integration must report zero skips.

## Independent consultation

One completed `claude -p --model opus --no-session-persistence --tools ''` consultation advised a shared explicit fixture plus audited inventory, not six duplicated globals or jsdom. Source/response retained outside this repository in the owner's existing consultation transcript directory. The source inspection corrected two suggestions: Audio is not constructed at bootstrap (only player storage is read), and browser history clones state rather than retaining object identity. We did not adopt a permissive proxy or catch-and-ignore errors.

## Separate inherited-suite incompatibility (do not fake green)

Source inspection also finds assertions older than the production candidate, independent of the missing APIs:

- `test_agent_permissions_view.cjs` expects `Level for Oscar`, `Level for Wizard app key`, `Review agent drafts`, `Add an agent`, a visible four-policy picker, and `Draft-only (Recommended)`.
- Current shipping `levelRow()` labels a picker `What <name> may do`, intentionally hides Draft-and-send unless already enabled, and uses lowercase `(recommended)` only for Wizard-agent rows.
- Current Settings lists `wizard_agents`; older keys moved to `#advanced`. Agent drafts moved into chats; no Settings `Review agent drafts` button exists. The source retains an internal drafts-list function, but a synthetic fixture must not expose hidden functions or invent controls to make stale UI assertions pass.

All original assertion lines remain byte-for-byte unchanged. The parent-authorized scoped release runner now executes the identical inherited Node test inventory on the exact live baseline `4566306576d3a6805da1ba531da3a89214dfd7af` and candidate, using the same five-file comprehensive fixture. It permits only source-proven obsolete permission-control failures with identical test IDs, assertion locations and error signatures; candidate-only failures, changed signatures, missing tests, new skips, missing browser APIs and unrelated common failures stop the build. Baseline-only incompatibilities are enumerated separately. New Signal schema/projection, shared fixture contracts, current public-route permission UI and current security tests must pass. The sole existing converter-optional skip before build is not acceptance: actual Go converter execution and post-build integration must execute with zero skips. Checkpoint labels are `scoped_pass` and `inherited_baseline_failures`, never a claim that failed original assertions passed. This replaces the earlier blanket-green prerequisite, not product behavior or feature acceptance. One staged heavy specification proceeds from that gate to the real pinned Rust/Go bridge build, binary/image/archive verification and synthetic browser QA. No live services, accounts, messages, databases or drafts are involved.
