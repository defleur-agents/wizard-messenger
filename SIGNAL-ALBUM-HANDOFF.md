# Signal album candidate handoff

**Source candidate only; no live account/data access or activation.**

- Worktree: `/home/telos/worktrees/messenger-signal-albums-20261105`
- Branch: `fix/signal-native-albums-20261105`
- Exact live source base: `4566306576d3a6805da1ba531da3a89214dfd7af`
- Confirmed engine config ID: `sha256:75dde49255cdb88b789103170b69c68517a7acc6a8523fec3ee0f2174235b84e`
- Container mount metadata showed no `/app` or static overlay mount. No mounted
  owner files, private message/Signal database, media, drafts or vault were read.
- Public pinned Signal source was the only bridge source inspected.

Implementation: `plumbing/signal-bridge/README.md`. The explicit native-ID marker
is emitted by the converter, validated/scoped by ingestion, persisted/publicly
projected with ordinal/count and reused by the generic album renderer/actions.
Captions, filenames, tile order, links and native per-part IDs remain intact.
Deleted Signal rows retain only non-content ordinals to keep surviving tile order.

Executable artifacts:

- Pinned full Rust/libsignal + Go `plumbing/signal-bridge/Dockerfile`, source
  patch, upstream AGPL license and actual converter fixture.
- `tests/test_signal_albums.py`: strict schema/privacy negatives plus real
  converter-output ingestion, retry/reorder, restart, reactions and native-map
  redactions. No manually invented marker substitutes for the converter proof.
- `tests/signal_albums.test.cjs`: real existing projection, caption and boundary
  regressions; reads persisted public ingress output for the converter comparison.
- `tests/signal_album_browser.cjs`: synthetic actual app with shared Appearance
  host/client, two skins/live switch, phone/wide, standalone dark, viewer,
  touch selection and three-file/one-caption forwarding via recording seams.
- `tests/run_signal_albums_forum.py`: immutable-stage verifier and full queued
  build/QA runner. Logs/JSON/screenshots go to the stage's `evidence/` directory.

Verified locally: JavaScript syntax, Python AST parsing, clean diff whitespace,
patch application against the exact pinned public source, upstream LICENSE byte
hash equality, base image reference metadata. Runtime tests, Go compiler/vet,
full pinned native build and screenshots are **not** a claimed pass until the
forum job returns evidence. See `evidence/signal-albums-source-preflight.json`.

Release boundaries:

1. Parent owns serialized live writes. This branch never touches live Runtipi
   config, owner overrides, Signal enabled state, accounts or service lifecycle.
2. It intentionally starts from the exact live source, not dirty shared files,
   and does not include PR100's independent attachment repair or PR102's worker
   activation. Parent must compose those source changes without replacing them.
3. Stage source is immutable and has a ready `submit.json` with an exact source
   revision and hashes. Only run on forum `/srv/work` via durable heavy admission.
4. Built Signal image/binary hashes remain explicitly unbuilt in provenance until
   produced. Before activation, complete built provenance and verify the patched
   version/hash rather than the generic old upstream `IsRelease` assumption.
5. No historical unmarked events are guessed/grouped. No real Signal send or
   owner authentication is authorized. Hosted-proxy screenshots are not physical
   device or authenticated installed-shell proof and need visual review.
6. Stage/evidence is scratch. Copy valued results to durable retention after QA.
