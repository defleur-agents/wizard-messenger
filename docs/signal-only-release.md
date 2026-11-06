# Signal native-photo-album activation (Signal-only, parent-executed)

Scope: the verified Signal album repair on exact live source `4566306576d3a6805da1ba531da3a89214dfd7af`
(image `sha256:75dde492…b84e`). Independent of the unfinished attachment/account work: nothing from
`fix/account-attachment-*`, draft-attachment or worker-activation branches is carried.

Shipped bytes
- Messenger: three-file overlay `unified.py`, `static/unified.js`, `plumbing/connectors-provenance.json`
  (first two byte-identical to QA-verified `a23fd8e26a72`; `unified.css` and every shared-client reference unchanged).
- Signal: frozen custom native image `sha256:14f0f945…27f6ba` (binary `a5993d2b…198759`,
  not the upstream release binary; AGPL corresponding source `signal-corresponding-source.tar.gz` SHA `6759f032…59bf1`).
- Everything else, including Telegram albums, Slack/Instagram worker overrides, owner settings and the gateway, is untouched.

Order (parent only)
1. Admit `submit.json` of the stage (forum, light). Verify `evidence/qa-receipt.json` SHA and that `scoped_qa_pass` is true.
2. Import both images on this host from the forum archives (stream `ssh forum cat … | docker load`; verify archive SHA256 first):
   `messenger-signal-albums-image.tar` (from the job) and `signal-image.tar` (SHA `556ccc99…de3312`).
3. `python3 tools/signal_only_lifecycle.py plan --evidence <stage>/evidence --expected-receipt-sha256 <qa-receipt sha>`
   (writes `activation-plan.json` only; no activation). Re-run against live if anything drifted; never overwrite a consumed plan.
4. Parent reviews the retained screenshots, then writes an authority file
   `{"plan_sha256","action","screenshots_reviewed":true,"parent_authorizes_existing_lifecycle":true,"gateway_served_assets_verified":true}`
   and runs `promote --no-concurrent-config-writers --authority <file>`. Rollback uses the same form with action `rollback`.
5. `verify` re-reads state at any time (read-only).

What the helper guards: owner settings (`isEnabled`, `appEnv`, `dockerCompose` = Slack/Instagram overrides) hash unchanged;
gateway/shared-view pins unchanged; only `messenger` and `signal` may change image/container; every other running service must keep
container id and start time; registry commit equals the plan revision; direct `/messenger` static bytes equal the plan. It never writes
the settings API, never edits the gateway matcher, and updates only through `wam app update messenger:wizardapps --no-backup`.

Expected side effect: the Messenger app and the Signal bridge containers are recreated (brief outage; Signal's linked session and
data volume persist). No other service restarts.

Rollback: retained containers pin both prior and new images; `rollback` restores the pre-change recipe with the Messenger base pinned by
image ID and Signal by its original digest reference. Old code ignores the new `album_index/album_count` media keys. Signal rows already
grouped as `signal:<id>` albums stay grouped under the old renderer (adjacent same-album rows), only tile order reverts to time order.

Not covered: historical unmarked Signal events are not regrouped; no real Signal send; the QA browser pass used an older shell snapshot than
the current live shell (see `shell-compat.json`); the current-live skin check is the parent's authenticated-gateway review.
When the attachment composite is activated later it must be rebased on this revision (its `plan` asserts base image `75dde492…`).
