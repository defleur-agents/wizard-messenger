# Attachment native-prefix fixture continuation

## Preserved failure

`heavy_d4ed93ea37794f278c0851e679d79322` failed, exit 1. Its frozen stage is
`/srv/work/messenger-account-attachment-composite-host-fixture-38676ee-r3`.
Spool log SHA-256: `5c151ded2117e5793b767d140789c273ac07cc3c11ebe78ea78bad8356b92199`.
Attachment command log SHA-256: `b979012b7955ef51e5e02d278c3c5cfa0a5d0c83836e75404255044337aa57b7`.

The exact fatal is `route.fetch: socket hang up (ECONNRESET)` at browser line 33,
on a rewritten loopback GET `/api/unified/people`. The asynchronous /app/ route
callback rejects outside the main scenario's try/catch, terminating Node without
its failure diagnostic. The server log contains only `ready`; no historical
request journal or traceback identifies why the peer reset. Do not invent a
backend error, a successful upload in this run, or an attachment product failure.
Raw logs can contain **disposable** browser cookie material; inspect only a
sanitized projection and never copy them into chat.

## Narrow fixture repair

REUSE: the complete real `ViewHandler`, parser, HTTP transport, sessions/CSRF,
draft store, attachment methods, send dispatch and existing synthetic providers.
EXTEND: only the disposable server's opt-in `/app/` adapter, performing one
prefix removal after `BaseHTTPRequestHandler.parse_request` accepts the request.
NEW product components: none.

`web.py` supplies root routes (`/`, `/api/...`, static assets) while the actual
Appearance host requires a registered non-root app prefix. The old Playwright
APIRequestContext `route.fetch` bridge is unnecessary and changes the HTTP
transport under test. The new test-only subclass changes only the accepted
request target; methods, unread raw bodies, Origin/cookie/CSRF headers, query
bytes and all real dispatch methods remain untouched. Root/standalone routing
continues to work. Existing fixtures opt in through `ATTACHMENT_FIXTURE_MOUNT`;
there is no production change or provider traffic. The five new source-derived
parser tests cover all four verbs/body/header preservation, near-prefix/root
negative controls, once-only rewriting, unchanged production method identities,
and the native malformed-version refusal. Their execution is parent-queued,
not claimed here.

The .win wrapper, registered /app/ entry, real shared host/client and all original
skin/ACK assertions remain. Every existing upload/failure/remove/retry/reload/
single-send assertion and deadline is unchanged. The successful browser receipt
additionally retains its existing sanitized method/path/status journal. This
fixture repair removes the observed failing bridge; it is **not** a claim that
the previously unobserved cause of ECONNRESET was diagnosed or that QA passes.

## Exact evidence inheritance and remaining job

Preserve the d2382b92d8d6 stage and its seven account-layout cells, 17 controller
cases, connector checks, strict old-source negatives, and exact historical-case
comparison. A new seal includes the original manifest/evidence hashes and the
complete source/member/executable-bit equality closure outside these exact QA
paths: this document, both attachment fixture modules, agent_drafts_stage.py,
draft_attachment_recovery_browser.cjs and run_account_attachment_forum.py.
The account browser, controller, their helpers and the entire production tree
remain unchanged. Inherited coverage is historical, never relabelled fresh.
The r3 failure and all earlier failed seals remain intact.

The fresh forum/light job runs the five native-parser contracts, then only the
unfinished real overlapping-upload/recovery/browser scenario, existing two-cell
single-send browser, focused Python modules, and the unchanged exact-live-base
static overlay/export. It does not rerun the passed account matrix, widen QA,
rebuild Signal/native engines, activate, change owner overrides or touch another
service identity. Parent admission and later fresh-live compatibility/lifecycle
checks remain required. A staged seal is not a verified release.
