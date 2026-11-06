# Owned-daemon bridge correction

REUSE: the existing isolated mount/network/PID namespace, `wzmsg0` topology,
resource/worker locks, controller, image archives and product source.
EXTEND: only the daemon launcher and its startup/cleanup diagnostics.

Docker 29.9.0 (`dockerd` SHA256
`86eb329d12e512790966fa60df4e9add4bed71c310ac1fd910b5dc79cd493202`)
rejects `--bridge wzmsg0 --bip 172.30.0.1/24` at daemon initialization.
Its `--validate` mode **accepts** that invalid combination, so configuration
validation alone cannot reproduce the startup failure.

Create `wzmsg0`, assign `172.30.0.1/24`, and bring it up **inside the existing
owned network namespace**, then use `--bridge wzmsg0` only. Keep the independent
`172.31.0.0/16,size=24` network pool and all other options. Never create or remove
a host bridge; the unchanged host observation still checks `wzmsg0`, not host
`docker0`. Namespace exit owns bridge destruction.

A bounded prerequisite inspection also found that Forum's `iptables` and
`modprobe` live in `/usr/sbin`, absent from the launcher's clean PATH. Add the
standard sbin directories to that namespace's daemon PATH only; no host setting,
package, service or privilege change.

The native continuation validates all actual options, replays the exact original
invalid option sequence as an expected negative control, requires its specific
exit/error, and then starts the corrected daemon. It records readiness and daemon
exit separately from the nested-container query. Failed queries remain false,
not successful emptiness; resource absence is a separate field. Original receipts
remain immutable, including failures.

`test_daemon_startup.py` performs six narrow controls: syntax/namespace/bridge
contract, actual pinned-binary full-option validation, and four failed-query
classifications. Supply `PINNED_DOCKERD` pointing to the verified binary and
adjacent `messenger-pinned-docker-init-29.9.0` and
`messenger-pinned-docker-proxy-29.9.0`; `RUNNER_UNDER_TEST` selects the derivative.
The control plane never starts a privileged daemon. Actual corrected startup and
native replay execute only after the canonical parent admits the existing job.

A preparation attempt initially failed because the control used nonexistent
synthetic binary paths; this failure counts, is not native/product failure, and
is not erased by the corrected control. Do not reset the five-failure budget by
renaming the continuation. At the cap, return the precise blocker and the direct
product-delivery path instead of starting another broad acceptance campaign.
