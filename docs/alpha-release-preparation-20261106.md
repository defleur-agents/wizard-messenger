# Prepared Alpha release checklist — not publication

The catalog `humanitylabs-org/wizard-alpha:main/apps/messenger.json` still points to `490abc84160a9afce037be7b187211518fd30b20`, version/tag `0.2.0-unified.10` / `v0.2.0-unified.10`. Its existing entry is the compare-and-swap expected value, **not** `absent`. Do not update it until the reconciled release is verified.

## Source and version

1. Start a release branch at the merged default `feature/unified-inbox`, not `fix/composed-messenger-release-20261105` or the old mention branch. Ensure #108/#109/#112/#113/#115/#117 are ancestors. Fetch before each push and include concurrent helper commits only after their source tests pass.
2. The pending “15.16” batch must not downgrade the default's `0.2.0-unified.16.24`. Choose a monotonic unreleased version (candidate `0.2.0-unified.16.25`), update config `version` and `tipi_version`, server version/ready header, client version, Docker overlay label and `wizard.md` together. Do not relabel a released image.
3. The integration preserves the current Store recipe's immutable public pins. Those existing Messenger pins are **not the new release**. Before packaging, bind all four shared Messenger-image uses (unified-init, messenger, translation, connector-init) to the final release image/tag. Every exported arch archive must contain exactly the image tag that the installer recipe resolves, not an arch-suffixed tag or an old digest. Keep the consolidated LINE service and its configured-marker command. Public bridge references must resolve for a fresh subscriber without developer-local tags; verify them independently.
4. Keep `private_data: true`, UID/GID 1000, root-only offline init helpers and private mounts. Do not reintroduce an external permission repair or inspect existing owner storage to verify this declaration.

## Verification before any publish

- Run `tools/check_source_tests.py` with `tests/requirements-unit.txt`; exact release-head CI must pass.
- Queue the staged forum synthetic browser job: mentions, real member backfill, owner mention rendering, clipped outgoing reactor tooltip, reactor tabs/sheets, phone Back/outside close; Instagram setup; phone/desktop on two real shell skins plus live skin switching. Inspect screenshots; a harness PASS is not visual proof.
- Resolve the actually served live source through the authorized parent, then require whole-source `app-parity-gate` PASS before live cutover. No waiver is implied by this integration.
- Real LINE/Instagram owner pairing remains a parent/owner gate, not a result of synthetic tests. Preserve already verified data/backup and updater permissions. Do not claim installation from health alone.

## Native build/export (parent queue admission only)

- amd64: native Linux on **forum** `/srv/work`, through `wizard_heavy_submit host="forum"`.
- arm64: native builder; use available native Linux arm64 GitHub runner or a queued Thales/macOS Apple-silicon candidate check as appropriate. Never emulate amd64 on Thales. Existing `.github/workflows/image.yml` uses native `ubuntu-24.04` and `ubuntu-24.04-arm`; it already builds multiarch GHCR manifests, but does **not** create Alpha's downloadable image archives. Native architecture and OCI source revision must be inspected.
- Stage exact `git archive` source only. No live container export, owner data, DB, environment, logs or app-data. Use hardened disposable-data smokes on the build host, never an owner install.
- Per architecture record actual Docker image ID and exact recipe image tag; `docker save | gzip -n` to revision-qualified Messenger archives. Compute archive SHA-256 and byte length; verify on transfer, load and smoke. Archive names may vary, but cannot overwrite another concurrent revision.
- Create immutable Git tag `v<VERSION>` at the final checked source commit, then a GitHub prerelease on wizard-messenger with `messenger-<revision>-amd64.tar.gz`, `messenger-<revision>-arm64.tar.gz`, and `SHA256SUMS`. Read back release asset IDs, sizes, digests and release URL. No tag, asset or package metadata has been fabricated/pre-created here.

## Checked manifest and catalog fields

Local publish input wrapper:

```json
{"schema":1,"scope":"private-test","apps":[]}
```

Populate `apps` with the fully verified Messenger entry object. Entry fields:

- `id`: `messenger`; `name`: `Messenger`; `summary`: starts `Alpha ·` and describes the actual consolidated release.
- `repo`: `humanitylabs-org/wizard-messenger`; `commit`: final full source SHA; `version`: exact released version; `tag`: exact immutable release tag.
- `architectures`: `["amd64", "arm64"]`.
- `images.amd64` and `images.arm64`, each with actual `asset`, `sha256`, `image_id`, `image`, numeric `asset_id`, numeric `bytes`. Do not reuse old .10 values or infer IDs/digests from filenames.
- `gateway`: `{"path":"/messenger/","strip_prefix":true}`.
- `release_url`: actual release URL; catalog `release_notes`: the concise approved notes (publish receives `--notes`).

Once all gates pass, the **parent**, not this preparation, may run:

```
wizard-alpha publish --catalog /absolute/checked-private-catalog.json --app messenger --repo humanitylabs-org/wizard-messenger --commit FINAL_FULL_SHA --expected 490abc84160a9afce037be7b187211518fd30b20 --notes "Approved exact-release notes"
```

Re-read the existing catalog pin immediately before this compare-and-swap; if it moved, refresh/reselect rather than substituting. Handle the generated private catalog PR internally, wait for checks, merge only under the release authorization, then GET the exact `apps/messenger.json` back and refresh the subscriber. Verify Alpha visibility and recipient source/asset access. Publishing an entry is not Miguel's installation or a provider login; do not contact him unless requested. This task intentionally does **not** publish, refresh/install, restart or change a catalog entry.
