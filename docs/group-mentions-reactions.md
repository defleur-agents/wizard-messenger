# Group mentions and reaction identities

## Copied interaction patterns (not Telegram code)

- [Telegram's mention announcement](https://telegram.org/blog/replies-mentions-hashtags): `@` selects a group member; a mention is a link, not an unstructured name.
- [Telegram Desktop autocomplete](https://github.com/telegramdesktop/tdesktop/blob/dev/Telegram/SourceFiles/chat_helpers/field_autocomplete.cpp): member results, Up/Down navigation and Enter/Return selection. Messenger also accepts Tab (a keyboard convenience; the inspected Desktop handler explicitly implements Enter/Return, not Tab).
- [Telegram unread mentions](https://core.telegram.org/api/mentions): an `@` indicator jumps to mention-bearing messages. Messenger adds the indicator to the existing group header/list; existing read timestamps clear its count.
- [Telegram reaction list API](https://core.telegram.org/method/messages.getMessageReactionsList) and [Desktop reactions controller](https://github.com/telegramdesktop/tdesktop/blob/dev/Telegram/SourceFiles/history/view/reactions/history_view_reactions_list.cpp): identities grouped/filterable by emoji. Messenger's existing chips now expose a names/avatar tooltip on desktop hover or keyboard focus, a right-click list, and a phone tap/450ms hold sheet with All/emoji tabs. Phone focus screenshots demonstrate accessibility, **not a nonexistent phone hover gesture**.

No upstream UI code is copied. Existing message/reaction/composer and Back helpers are extended; no new messaging authority, provider session, permission or account operation is added.

## What the app actually knows

The Matrix bridges deliver membership through `m.room.member` state and reactions through sender-bearing `m.reaction` events. The member directory uses joined IDs, state names and the existing opaque avatar proxy. Outgoing send/preview-confirm/edit recomputes exact `@label` tokens against **that channel's** directory; ignores client-provided identity claims; sends standard `m.mentions.user_ids` plus escaped `matrix.to` links. Duplicate names receive disambiguated labels. Stored spans use UTF-16 offsets. Translation that changes mentioned IDs asks the owner to use Send original instead of silently dropping a tag.

| Network | Native outgoing mention support in this update | Reaction identities |
|---|---|---|
| Telegram | Yes, known joined bridge members. [Pinned converter](https://github.com/mautrix/telegram/tree/6991248e6a573489d2d38d603b5dbed1627113bc/pkg/connector/matrixfmt). | Actual `m.reaction.sender`, resolved using cached room metadata; Telegram upstream supports per-user reactions. Missing names remain count-only. |
| Signal | Yes, [v0.2610.0 Matrix formatter](https://github.com/mautrix/signal/blob/v0.2610.0/pkg/msgconv/matrixfmt/convert.go), `AllowedMentions`. | Sender-bearing bridge events when available; no invented names. |
| WhatsApp | Yes, [v0.2610.0 converter](https://github.com/mautrix/whatsapp/blob/v0.2610.0/pkg/msgconv/from-matrix.go), explicit allowed mentions and `MentionedJID`. | Sender-bearing bridge events when available. |
| Slack | Yes, [v0.2610.0 formatter](https://github.com/mautrix/slack/blob/v0.2610.0/pkg/msgconv/matrixfmt/blocks.go), `GetMentionedUserID`. | Sender-bearing bridge events when available. |
| LINE | No audited native mention round-trip in the pinned bridge; picker disabled. The bundled LINE **setup repair** is separate. | Render known reaction senders only if supplied by the bridge; otherwise counts and an explicit unavailable explanation. |
| Instagram, Facebook, X, LinkedIn, Google Messages, Dots | No audited native mention conversion; picker disabled, ordinary text unchanged. | Same conditional bridge rule, **not a claim each network exposes reactors**. |
| Marmot/Nostr | Current public Messenger engine admits two-member DMs, not a group mention/send-tag protocol; no group picker or native-mention notification claim. | Engine list-valued `by_emoji` provides real member pubkeys; resolve a cached name or display the actual pubkey. Scalar aggregates stay count-only. |

Incoming explicit protocol owner/owner-ghost mentions highlight the existing bubble and count toward the existing group `@` badge. Plain-text names do not forge owner tags. Live arrivals reuse the existing push-intent queue, respecting mute/low-priority and already-enabled push; no new notification permission request. Historic rows are not guessed into mention records. Unknown reaction identities are never filled from counts; the sheet explains the missing remainder. Native mentions depend on actual bridge/provider support and pairing; synthetic tests are not a real-provider round-trip receipt.

## Component ownership

Reuse:
- composer-input: REUSE `WizardApp.composer.bind`; mention selection intercepts only an open picker before existing send handling.
- composer-send: EXTEND `static/unified.js composer`, `serverDraft`, existing queue and `client_id` latch; text/drafts/attachments remain on their existing paths.
- reactions: EXTEND existing unified reaction strip/`reactionChip`, native reaction strip and existing `holdToMenu`/overlay.
- back: REUSE `WizardApp.back.register` and existing app `back`/overlay callback; picker gets first refusal, sheet never exits.
- appearance: REUSE `WizardApp.appearance` v1 tokens and live client propagation; fully opaque floating panels retain a literal dark floor beneath token paint.
- images: REUSE existing opaque picture proxy and avatar renderer.

## Acceptance and evidence boundary

`tests/test_group_features.py`: disposable synthetic store/adapter, identity-safe parsing, UTF-16, duplicates, escaped HTML, standard native tags, protocol owner tags/push/mute/read/redact, reaction sender grouping and Marmot aggregates. `tests/group_features.test.cjs`: synthetic DOM keyboard/insert/mirror, outside/Back, hover tooltip, tabs, phone tap/hold, immediate pressed paint and long-press release. These do not establish layout or provider behavior.

`tests/group_features_browser.cjs` and `tools/run_group_features_qa.py` run only on forum through a parent-admitted durable job. They reuse LINE's hosted real-client Appearance pattern, current pinned shared shell source and two live-switched skins, desktop + touch phone, synthetic messages only, screenshots for picker/sent mention/tooltip/reactor sheet. The runner retains tests, source hashes and a complete source overlay payload. It never accesses a production container, account or message store. A staged runner is **not a passing browser receipt**. Inspect the generated screenshots before acceptance; no local browser fallback.

## Bundled update / normal activation (parent-owned, not run)

Candidate version `0.2.0-unified.15.15` / `tipi_version 56` stacks on PR109's source (notice removal + LINE setup repair). The public live health at preparation time reported `15.14`; its served app.js still announced `15.13`, so image version alone does not establish the pinned view version.

1. After exact-head CI + parent LINE acceptance + this feature's forum acceptance, build the existing `Dockerfile.overlay` on forum against its audited immutable carrier (or an explicitly verified newer carrier) with `--build-arg REVISION=<accepted-source-sha> -t wizard-messenger:0.2.0-unified.15.15`. The new module is in both Docker COPY lists. Export an image archive, immutable image/source/hash receipt and normal `runtipi/` recipe. No owner runtime inspection is required to build from public source and an audited carrier. Do not overwrite carrier/tag or infer carrier availability from source.
2. Publish the accepted image/recipe through the existing catalog/source-selection route (or the existing private versioned image-archive release route when registry publishing is unavailable). A GitHub tag **alone does not install an image or refresh App Manager's recipe**. Preserve current selection pins until the new service is healthy; parent release authority resolves the installed source selection, catalog and static-view pin through their admitted control plane.
3. Once the recipe/image are admitted, normal installed command is **`wam app update messenger:wizardapps`** (default `performBackup:true`); the underlying lifecycle is `PATCH /app-lifecycle/messenger:wizardapps/update {"performBackup":true}`. Do **not** use `wam install` as an update, `docker cp`, container shell/files/log/env access, or a restart workaround. `wam app update --help` unfortunately falls into runtipi passthrough and hits the unrelated Hermes promotion guard; actual `wam app update <id>` dispatch is explicit in installed WAM `cli.py`.
4. This normal update **recreates/restarts the app container** (and may restart bridge services); the WAM wrapper starts a formerly-running app again if Runtipi leaves it stopped. The encrypted Messenger vault will be locked until James re-enters his passphrase. No update/restart has been performed by this task.
5. Compose retains `${APP_DATA_DIR}` bind mounts (`/data`, internal homeserver/bridge storage) and the update's backup option requests preservation, not uninstall/delete. Existing data is designed to survive, but no production backup/data verification is asserted under the privacy seal. Parent must obtain its allowed backup receipt before activation. Avoid changing data mounts, forms, secrets or permissions.
6. Only after healthy public version/static checks, advance the existing app-version/source-selection identity and serve the matching app.js/app.css/index plus unified.js/css through the normal managed view update. This host has an older static view pin; image update alone may leave stale app.js. If the admitted App Manager route cannot advance that pin without private/container inspection, stop with that exact control-plane blocker rather than bypassing the seal. Parent decides activation and owner relock timing.
