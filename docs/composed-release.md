# Composed Messenger release — held, parent-owned

This packet supersedes the two **unactivated** serial release proposals. Build ONE
Messenger image on live `4566306576d3a6805da1ba531da3a89214dfd7af`, and pair it with
the already-frozen Signal bridge. Never activate either prior proposal first.
Protected merges and all live lifecycle actions belong to the parent.

## Production diff (five-file image payload)

| Path | Provenance / composition |
|---|---|
| `static/connectors.js` | exact account/attachment `72d6770fb96670ee0b6cc9c99bde4eab452a005e` |
| `static/unified.css` | exact same attachment/account revision |
| `static/unified.js` | exact attachment JS + exact disjoint Signal delta from `89d67976ea8b799f047509bc22433f783d739b13` versus live; reconstruct bytes before execution |
| `unified.py` | exact QA-verified Signal implementation, retained in `89d67976ea8b799f047509bc22433f783d739b13` |
| `plumbing/connectors-provenance.json` | exact frozen Signal provenance from same packet |

The base `/app` tree must differ at exactly these five paths. Five explicit per-file
`COPY --chmod=0644` instructions retain all base directory traversal permissions;
five appended layers and actual non-root module imports are required. The
source branch also carries original QA, native patch/license and corresponding-source
provenance; none is implicitly copied into the production image. Existing recipe
files stay at live baseline: only parent lifecycle materializes the two image pins.
Shared `index.html`, `app.js`, `app.css`, gateway matcher and every native binary in
the Messenger base stay unchanged. This does not silently upgrade the pinned ready
version. No database, drafts, attachment/vault contents, provider page or private
agent inspection is authorized.

## Packaging cause and narrow correction

The admitted r3 job `heavy_2db36f91dddd4f13a1f45f3a9a340d2f` passed all
preparatory/behavior checks and built its overlay, then failed the actual packaged
uid-1000 `/app` read: recursive `COPY --chmod=0644 payload/ /app/` removed directory
traversal bits. Preserve that failed stage/image/logs; never activate it. Only the
Dockerfile, packaging runner, this document and a new packaged readability probe
change. Product bytes, identity helper, lifecycle adapter, recipe and every existing
test remain identical. No source recipe version bump: the parent adapter derives
the new source selection/revision and two immutable image pins from the fresh receipt,
then advances tipi under its existing guard. Stage manifest and final receipt bind
the new revision, Dockerfile, probe, unchanged lifecycle/helper and recipe hashes.

The smallest real regression runs the new probe in networkless/read-only containers
as uid/gid 1000: untouched `static/app.js` must reproduce PermissionError on the
preserved defective image; base and corrected candidate must read every `/app` file.
Compare every directory's mode/uid/gid exactly with base and require all five payload
files to be 0644. Keep exact five-file content diff, full Config, ordered base layer
prefix, five new file layers, app-user imports, export and archive identity proof.

Read-only measurement of the original imported base found absent raw OCI Config
`Cmd` and `Volumes` materialized as **null**. These were the only observed additions
missing from the failed account runner's defaults. All other raw Config fields and
ordered RootFS were equal. Frozen Signal image measurement independently found
absent `User` -> `""` and `Entrypoint` -> null (plus the already-known empty defaults).
The two committed image-metadata fixtures record the full raw/inspect objects.
`tools/docker_overlay_identity.py` never filters fields: it expands only absent,
explicitly observed empty fields, then compares the **whole** Config with JSON type
sensitivity. Raw field removals, non-default expansions, unknown fields, unrelated
IDs and layer order/count drift fail. Archive blobs, descriptor sizes, one reachable
manifest, raw config identity and legacy ordered layer reachability remain strict.
These fixtures are measured image metadata, not invented provider data.

`FROM sha256:<config>` is not a Dockerfile local-image reference. The runner tags
the verified imported identity as `wizard-messenger-base:composed-<head12>`, checks
its identity immediately before building, requires the actual `default` **docker**
driver (not docker-container), and calls `docker buildx build --builder=default
--load --pull=false --network=none`. No registry fallback, native rebuild, daemon
change, broad Config normalization or old-evidence edit is allowed. The pinned
buildx does not support `inspect --format`; the runner validates its observed text
schema instead.

## Evidence / case ledger

`inheritance.json` in the sealed stage binds original manifests, logs, artifacts,
source closures and the inherited-vs-new ledger. Source equality is not fresh QA.

Inherited, not rerun:
- Seven account layout cells, connector controls, 17 controller cases, strict old
  product negatives and exact historical-case comparison from the attachment line.
- Five native `/app/` parser contracts and focused Python results from r4. Focused
  Python receipt describes its original source, not new merged Python execution.
- Frozen Signal build/binary/image, real converter ingestion (zero integration
  skips), 64 unittest + 13 pytest security cases and corresponding AGPL source.
- All earlier failures remain frozen; obsolete UI expectation failures are neither
  hidden nor relabelled green (`all_suites_green:false`).

Additionally inherited from exact-source r3, not rerun:
- Ten Config/local-builder regressions, six composed lifecycle regressions,
  17 attachment controllers, six Signal projections with actual converter rows.
- Real merged attachment recovery, original two-cell single-send and four-cell
  merged Signal browser (Nebula/Signal, all-file forwarding, live skin changes,
  tile viewer, standalone dark). Parent must still inspect those saved screenshots.
- Exact archived-live/candidate parity. The new source delta is packaging/docs only;
  the complete prior tracked-source closure is hash-bound except those explicit files.

New, only when parent admits this packaging-only continuation: corrected five-file
overlay, real packaged non-root readability negative/positive, complete `/app` diff,
directory metadata equality, imports, export/reproof and frozen Signal
Config/RootFS/binary requalification. No feature QA, browser or Rust/Go rerun.
All inherited logs, checkpoint and screenshots have frozen hashes. Preserve the five
obsolete permission-test failures explicitly; final result is scoped_pass, never
all_suite_green. The failed r3 overall job remains failed, not retroactively green.

Reuse:
- attachment-chip: REUSE WizardApp.attachChip.node
- back: REUSE WizardApp.back
- appearance: REUSE WizardApp.theme
- forwarding: REUSE WizardApp.share

App-owned controllers remain in Messenger. Extend only existing draft serialization,
account sign-in geometry and album projection. NEW shared capabilities: none.

## Parent-only lifecycle and rollback

Stage `submit.json` is the exact forum/light admission input (900 seconds). Do not
start tests/builds/browser directly. A helper returns the seal/spec to its parent;
it does not forge admission. Until a new job produces a passing `qa-receipt.json`,
this is prepared source and a continuation, **not a built/verified final release**.

After completion, parent checks new packaging logs, inherited exact case totals,
saved r3 screenshots and `app-parity.log`; import the new exported Messenger archive and frozen Signal archive
only after hash verification. Re-prove typed target identity against each archive's
full raw Config and ordered RootFS; worker inspect wrapper equality alone is not
target proof. Preserve full archives on durable encrypted storage, not forum only.

`tools/composed_lifecycle.py` is the existing Signal guarded adapter, narrowed to
one composed five-file image and the frozen Signal image. The stage's parent packet
contains its exact source/hash. It is **unrun** here. Its `plan` is read-only toward
live configuration and writes only a fresh private plan; `promote`/`rollback` require
fresh parent plan-bound authority and a no-concurrent-config-writers agreement.
Do not reuse either serial release's plan or authority.

Parent flow, never executed by this helper:
1. Re-resolve live source/image, source recipe, all eight service identities/start
   times, owner settings hash, protected Slack/Instagram override bytes and gateway
   pins/actual served assets. Stop on drift, don't overwrite or merge live data.
2. `python3 tools/composed_lifecycle.py plan --evidence <copied-evidence>
   --expected-receipt-sha256 <new-qa-receipt-hash>` from the exact clean pushed tree.
3. Verify current authenticated gateway static bytes and real shared client closure;
   create parent authority containing exact `plan_sha256`, `action`,
   `screenshots_reviewed:true`, `parent_authorizes_existing_lifecycle:true`,
   `gateway_served_assets_verified:true`. No provider browser or content view.
4. Parent only: `promote ... --authority <file> --no-concurrent-config-writers`.
   Existing WAM lifecycle only; no settings PUT, matcher edit or shared service restart.
5. `verify` reads achieved state. Only Messenger and Signal may change containers.
   **Every other service** must retain ID and start time; Slack/Instagram override
   settings remain byte/hash guarded. Six original running services are preserved.

Rollback is a separate one-shot parent action bound to the same plan: restore the
exact before recipe/selection, advance tipi again, pin old Messenger immutable ID
and original Signal digest. Retention containers protect both old/new images but
are never started. Do not force rollback over partial/foreign state. No data-volume
rollback/migration is performed. Existing Signal album metadata is additive; older
code ignores ordinal/count and preserves adjacent grouping with old time ordering.
Settings GET/hash then guarded lifecycle is not atomic against independent writers;
parent must serialize owner configuration edits. The local promotion lock alone
cannot establish that agreement. Existing opened windows need close/reopen after a
future activation, not now.
