# LINE: first-run setup and evidence boundaries

## Scope and reuse

- REUSE the pinned `beeper/line` bridge and existing `Connectors` owner-only enable/status/login adapter; no second bridge or provider integration.
- EXTEND the existing Accounts → Add → LINE card. `Needs one-time setup` now has **Set up LINE**. Selecting a network alone never enables it.
- REUSE the existing card, error, Back and button styles; no CSS/palette changes. Skin changes must leave the same document and setup state intact.
- Preserve the previously approved agent-notice removal from release `603039eba7fe01876d236cd43533c5269a0b5556`.

## What was broken in source

1. The selected unconfigured LINE card rendered its status with no setup action. The generic Add path enabled a network without first presenting the selected LINE card; once that card was displayed, there was no recovery action.
2. The checked-in LINE Compose command checked `/data/configured` once and then slept forever. An owner enable action only creates that marker: an already-running dormant worker could never wake up. The fix waits for the marker, then execs the same maintained LINE binary. Other workers are outside this patch's scope.
3. LINE enable could mark itself enabled even when its private provisioning prerequisite was missing. Preflight now refuses that transition without returning any private value.

These are source-level defects, not proof that either is the only cause of a particular live server's state. Live container state was deliberately not inspected.

## Owner-controlled flow

Back to accounts → Add → LINE → Set up LINE → wait for actual bridge readiness → choose QR or email sign-in. Setup never starts a provider login, scans a QR, enters credentials, pairs an account or sends a message. A one-minute end-to-end deadline produces an explicit retry/repair screen. Late results cannot reopen a closed view or overwrite timeout recovery.

If installation prerequisites are absent, the owner sees a repair-required message, not a false connected/ready state. A bridge is ready for sign-in only when real status advertises supported flows; a configured flag alone is insufficient.

## Bounded verification

Run only on forum through durable queue admission, never on the conversational host:

- Existing `tests/test_connectors.py` and `tests/test_connector_login_runtime.py`, plus `tests/test_connector_login_runtime.cjs`: synthetic adapter/UI regressions, including the exact `Needs one-time setup` action, enable/readiness, unavailable service, missing prerequisites/flows, timeout, late result and close.
- Existing `tests/account_setup_browser.cjs` with `LINE_SETUP_ONLY=1`: hosted synthetic UI, current shared Appearance host/client, phone and desktop, two real skins changed live, actionable/ready screenshots, standalone dark fallback. Provider calls are blocked. This is **not real-provider evidence**.
- `tools/prove_line_first_run.py`: disposable Synapse and the pinned maintained LINE binary on an internal Docker network. It begins with no enabled marker, runs the exact source-defined dormant command, invokes the existing enable adapter, and requires actual disconnected/bridge-live status with both supported QR/email flow IDs. It never starts any login and has no provider egress. New image builds must be source-pinned and recorded separately from the historical image/binary provenance; never silently rewrite old pins.

Do not claim these checks passed until their result files exist and have been read. Do not retry more than two aggregate LINE runs; unrelated synthetic shell acceptance is separate work.

## Live privacy/activation gate

Only the public health and static assets were read on the live service; no Messenger container, private messages, databases, logs, credentials, sessions or private agent homes were inspected. Existing message access remains unchanged.

A source PR is not live readiness. Before activation, the parent must obtain an explicit narrow exception if applying this fix requires crossing the current no-container-inspection boundary. Scope any exception to the specific public product code files and the LINE worker's startup definition, never private data/configuration. A Python code replacement may require a coordinated Messenger restart and owner unlock; do not surprise the owner with a relock. Do not inspect production container files to fill that gap without permission.

After permitted activation, verify served public assets and a content-free LINE readiness result through an admitted control-plane contract. Then stop at owner sign-in: James personally chooses QR/email and completes it without agent browser inspection. Do not treat source support, enabled configuration, live bridge readiness and account pairing as interchangeable outcomes.
