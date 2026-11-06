# Signal native albums (source candidate)

## Scope and provenance

REUSE: `MessageConverter.ToMatrix`, upstream `bridgev2.MergeCaption`, native
`signalid.MakeMessageID` and `MakeMessagePartID`, `UnifiedInbox.ingest`, persisted
per-photo rows, generic `albumPosts`, viewer, selection/forward and mapped delete.
No alternate bridge/provider, timing heuristic, Matrix-event coalescing, schema
migration, native account login or new gallery UI.

Upstream: https://github.com/mautrix/signal/tree/d129f0ecc6bd29cfb5e54b18e025bd0c8a20a4bf
(`v0.2610.0`), libsignal submodule `4beb029d8a941f81e7d9c6d8af1ed25a677569a8`,
mautrix/bridgev2 v0.32.0 (`aae5273d1463cd69dd2f95eb2dd62e8bd9084c4d`).
`albums.patch` and the converter fixture are AGPL-3.0-or-later. `LICENSE` is the
byte-for-byte upstream license. Corresponding source includes that pinned
upstream/submodule, this patch, tests and Dockerfile; preserve source availability.

The Dockerfile pins both build images and the installed upstream runtime image.
It builds the full libsignal static library, runs the same *real converter*
fixture before and after applying the patch, runs converter/connector tests and
vet, builds the patched Go binary and checks its final-runtime dependencies and
version. The modified binary is not the old upstream SHA256. The candidate
provenance therefore deliberately has a null built binary hash until the forum
job produces evidence; do not activate or mislabel that as an upstream binary.

## Contract

Only a non-view-once DataMessage with 2–100 attachment pointers, all successfully
converted to images (and optionally this same DataMessage's final body), is
marked. Mixed image/file/video, failed conversion, contact/payment/notice and
single-photo behavior remains upstream behavior. The body merges once onto image
zero using the upstream caption helper, preserving filename, HTML, mentions,
link previews, existing caption and GIF metadata. No native event or PartID is
coalesced or replaced.

Every image content gets:

```
"org.wizard.signal.album": {"id": "<native MakeMessageID(sender, timestamp)>", "index": 0, "count": 3}
```

This is Signal's native source identity, **not a sender/timestamp time window**.
Two independent source messages with the same timestamp have distinct sender
identities; the same sender/timestamp is the same native Signal identity.
Messenger only consumes a strict marker on valid Signal m.image media; it does
not trust it on text or other networks. Ordinal/count survive storage, the public
media allowlist, restart and deletion (a deleted row retains only non-content
ordinals, never its URI/caption). Delayed parts are sorted inside the existing
adjacent sender/identity/network/direction/photo scope. A text boundary is not
crossed. Telegram's insertion ordering remains unchanged.

All distinct captions remain visible in tile order instead of silently taking
only the first. Canonical originals/IDs remain per tile; previews use their own
part's media endpoint, forwarding emits all three files plus caption once,
reactions still target mapped parts and deletion redacts all mapped album events.
Signal itself reacts/deletes at native DataMessage granularity; this patch does
not invent per-attachment Signal identities.

## Forum job

From an immutable stage containing `source/`, `shell-web/`, `stage.json` and
`submit.json`, admit `submit.json` through `wizard_heavy_submit(host="forum",
lane="heavy")`. The runner is `tests/run_signal_albums_forum.py` and may take a
full native Rust/Go build, not just a JS packaging pass. Never execute its rig on
the VPS or bypass shared-worker admission.

The two converter JSON files come from the actual `ToMatrix` direct-media path
with synthetic red/green/blue attachment pointers, no Signal network download.
Baseline is three independent image events plus a caption event; patched is
three mapped image events with one source group and one caption. Python feeds
those actual outputs into real temporary UnifiedInbox stores, exports public
rows and checks retry/reordered arrival, restart, reaction, per-part deletion
and privacy scoping. The Node projection test consumes those exported rows.
Schema-only hand-authored markers are explicitly *not* ingress evidence.

The browser uses the real app and pinned shared Appearance host/client in a
synthetic same-origin proxy, captures phone/wide Nebula and Signal skins with a
live skin switch and retained form, and standalone dark. It exercises real tile
viewer and touch selection/forwarding with recording endpoints only. This is not
an authenticated installed shell, physical-device or owner Signal ingress proof.
All screenshots require independent visual review. The stage/evidence is forum
scratch; the parent must copy valued results to durable retention.

## Release boundary

No running service or owner configuration is modified by this job. The two
compose sources only change Signal's candidate image, with `pull_policy: never`;
configuration, enabled marker, volumes and healthy bridges remain untouched.
The parent owns combination with attachment PR100 and worker PR102, current-live
parity verification, the built image/binary hash readback, source-provenance
completion and serialized activation. `tools/verify_connectors.py` assumes an
unmodified release (`IsRelease`); a rebuilt patched binary must be checked against
its actual source/hash/version, never waived or called the old upstream release.
No attempt is made to regroup historical unmarked events: their associations
cannot safely be recovered from times alone.
