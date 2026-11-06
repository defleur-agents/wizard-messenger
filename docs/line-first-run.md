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

## Installed worker packaging

The normal manifest-selected `runtipi/docker-compose.yml` includes LINE, not only
`runtipi/connectors.compose.yml`. Both definitions use the same source-pinned
local image tag and marker-watching command. A release must build/import this
image before activation (`pull_policy: never`); enabling a network cannot create
a missing Docker worker. Run `tools/build_line_connector.py` on the designated
build worker. `MESSENGER_LINE_IMAGE` may pin the verified imported image digest.
Historical build IDs in `plumbing/connectors-provenance.json` remain historical,
not a promise that that image ID is present on every host.

The reproduced bridge build uses beeper/line source
`72c7a51a44f344966b916bd2f42a734381061186` and recipe
`plumbing/line.Dockerfile` SHA-256
`11addc6aa7280d28c23a203fea311d238c9a1b7c927485c4b2cc2f0fb2359afc`.
The deployment packet must record the archive hash, source config digest, loaded
host manifest digest (Docker storage versions may report different image IDs),
rootfs layer equality and executable hash; never silently overwrite old pins.

`connector-init` pre-generates LINE's private config and Synapse appservice
registration, including the registration in `app_service_config_files`, for
**all** supported optional networks, even while disabled. It sets data ownership
to UID/GID 1000. Matrix depends on successful connector-init before boot, so an
already initialized current stack does not need a Synapse or Messenger restart
just to add the missing worker. Synapse reads registrations at startup; a
registration first added after its startup would need a coordinated Matrix-only
restart. Never restart Messenger to add this worker.

For a narrow live repair, back up the owner-local Compose override, import the
verified image and add only LINE using the existing matrix-lane and
connector-egress networks. Leave owner-defined service entries outside WAM's
`x-wizard-networks.services` managed list. WAM includes this override on updates
and prunes only its own listed stale service entries. Validate without printing
resolved environment, then start only `line` with `up -d --no-deps line`.
**Check marker metadata first**: an existing `/data/configured` means a previous
owner enable already occurred; do not delete it or claim a dormant start. Stop
for an activation decision if the repair was authorized only for dormancy.
No worker healthcheck passing while dormant proves bridge readiness; real
readiness must advertise both supported flow IDs after owner enable.

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
