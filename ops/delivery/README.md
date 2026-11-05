# Isolated delivery controller

Harness-only custody for the failed current-composite r3 delivery. Runtime source remains the separately archived `da34eb4e7e1bc46e24cac13c605549fbcce917bf`; these files are not product overlays.

- `forum_delivery.py`: copied into a fresh sealed capsule by its coordinator, never run against an old results root. The private dockerd consumes only generated owned `{}` JSON plus explicit flags and a clean allowlisted environment. No host socket/config mutation is permitted.
- `fixtures/forum_delivery_r3.py`: exact original SHA256 `dc5e0ae2377864d30114e7bc9f88ee727a4cbedcc4cf8de432f02c05e1460de9`, retained only as the demonstrated-negative source. Never execute its native entry.
- `test_forum_delivery.py`: bounded source/unit tests using synthetic files and subprocess stubs; no Docker, namespace, browser or service starts. Run `uv run --offline --no-project --with pytest python -m pytest -q -o addopts= ops/delivery/test_forum_delivery.py`. Tests include actual original finalizer failure without a receipt and explicit new-controller receipt persistence with an unreadable artifact.
- `recover_r3_readonly.py`: exact owned r3 process/mount/cgroup/bridge/private-path/log-metadata census. Read-only, no Docker API. Its JSON is separate recovery evidence, never a replacement original receipt or a claim that original packaging ran.

The coordinator alone submits the sealed specification to the durable Forum worker. Native ownership/redirection, daemon startup, packaging, actual canonical shell/SDK screenshots, parity, lifecycle and cleanup remain unrun until that admission. `native_accepted` remains explicitly false because the previously skipped Signal converter public-ingress fixture is not supplied by these harness tests. Historical source/browser receipts are not a current-candidate aggregate pass. Future promotion must obtain that native gate as well as every existing mandatory gate and fresh live CAS.
