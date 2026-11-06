# Messenger attachment repair: component reuse

This live legacy app had no COMPONENTS.md at revision 4566306576d3a6805da1ba531da3a89214dfd7af. No replacement component is introduced.

## Inventory

| Capability | Existing implementation | Decision |
|---|---|---|
| Canonical draft revisions, persistence, owner-only send boundary | drafts.py; web.py existing /api/drafts routes | REUSE unchanged |
| Draft tray, autosave and reconciliation | static/unified.js serverDraft | EXTEND serialize revisions; item-scoped errors; recovery |
| Attachment chips and remove action | WizardApp.attachChip.node in the shared app client | REUSE existing chips, including unavailable-item placeholders |
| Composer send latch and queued send retry IDs | static/unified.js composer / queueSend | REUSE; EXTEND retain conversation identity across asynchronous retry |
| Album projection and renderer | static/unified.js albumPosts / bubble | REUSE unchanged; Signal bridge slice is separately documented |
| Appearance v1 and standalone dark fallback | existing app.css, unified.css and shared app-client.js | REUSE unchanged; hosted proxy two-skin/browser evidence is a QA gate |

Reuse:
- draft-controller: EXTEND static/unified.js serverDraft
- attachment-chip: REUSE WizardApp.attachChip.node
- composer-send: EXTEND static/unified.js composer
- album-projection: REUSE static/unified.js albumPosts
- appearance: REUSE shared app-client Appearance v1

## Group interaction extensions (same components)

| Capability | Existing implementation | Decision |
|---|---|---|
| Input/draft/send | WizardApp.composer.bind; unified.js composer/serverDraft/queueSend | REUSE shared input; EXTEND group member selection and existing textarea mirror |
| Reaction strip | unified.js bubble/reactionChip; app.js renderReactions | EXTEND sender tooltip + existing overlay; no second reaction renderer |
| Back/outside/hold | WizardApp.back.register; unified.js back/overlay/holdToMenu | REUSE; EXTEND picker-first close |
| Owner notices | unified.py ingest/push_intent; existing group rows/message bubbles | EXTEND explicit protocol tags/highlight; REUSE notification policy |
| Pictures | existing opaque avatar proxy + avatar renderer | REUSE |
| Appearance | app-client Appearance v1 / --wz-* roles | REUSE live theme; literal opaque popup floor beneath token paint |

See docs/group-mentions-reactions.md for channel limitations, copied Telegram patterns and bounded acceptance.

## 15.16 corrections

- EXTEND the same `mentionComposer` / `reactionChip` with one pane-bounded floating-panel placement helper; no replacement composer, reaction renderer or sheet.
- EXTEND `refresh_pictures`' existing bounded metadata backfill, plus `PeopleStore.members`' native/plain capability distinction.
- REUSE Appearance v1, opaque panel floors, existing draft/send/Back/overlay and normal WAM lifecycle. Native Signal and owner-local worker overrides are not changed by this source fix.

## Inbox click scheduling

EXTEND existing `drawList` scheduling in `static/unified.js`: keep a pressed chat row attached until its click dispatches; defer only inbox painting, never chat opening or backend ingestion. Cancellation, blur and a bounded lost-release timeout restore painting.

NEW: none.

## Labels: your own groups of chats (16.26)

James calls them groups; the code and the UI call them Labels (a label = a group of chats you filter the Inbox by; not the Groups group-chat filter).

| Capability | Existing implementation | Decision |
|---|---|---|
| Per-chat labels and the Inbox Filters > Labels chips | unified.py room_label + people() aggregation; unified.js paintFilters/matchesFilter | EXTEND: any chat (people, groups, merged people on every identity), chips also list empty catalogue labels |
| Label that exists while empty; create/rename/delete | NEW table label_catalog in unified.py PeopleStore (migration-safe, seeded once with WizardOS); owner-only routes /api/unified/labels* | NEW (nothing existed; one catalogue, no second label store) |
| Labels editor | unified.js editPerson sheet (Save labels text box for groups only) | EXTEND: checkbox picker + New label box in every chat's info sheet; same picker in the row/thread menus (actionMenu) |
| Manage labels | unified.js overlay()/closeOverlay() sheet, filter chip | REUSE overlay sheet and Back/outside-close; NEW sheet content |
| Appearance / tap targets | unified.css var(--wz-*) fallbacks, opaque sheets | REUSE |

Reuse:
- labels: EXTEND unified.py room_label + unified.js paintFilters
- label-catalogue: NEW unified.py label_catalog (only addition)
- sheet-overlay: REUSE unified.js overlay/closeOverlay/actionMenu

## Inbox view: Chats or Compact (16.27)

| Capability | Existing implementation | Decision |
|---|---|---|
| Chat list row with or without the last-message line | unified.js drawList() `compact` flag (u-compact class), set by the old Settings "Message previews in the list" switch (default off since 15.12) | EXTEND: one renderer, flag now driven by Settings > Inbox view (Chats default, Compact), key messenger.inboxView; the switch is replaced, not duplicated |

Reuse:
- inbox-rows: EXTEND unified.js drawList + previewsOn()/setInboxView()

Catch me up (0.2.0-unified.16.28):
- catch-me-up-sheet: REUSE unified.js overlay/closeOverlay/back (opaque .u-sheet, outside tap, Back one layer); NEW catchUp() content only
- catch-me-up-entry: EXTEND threadBase title bar (iconButton) + unreadDivider row (Summarize these); no new menu
- catch-me-up-permission: NEW catchup.py grant/cache (catchup_grant, catchup_summary); owner-session routes only, REUSE permissions.capability_for (no agent capability)
- catch-me-up-model: REUSE translation.py Tinfoil call pattern and TINFOIL_API_KEY via a new /complete route; NEW catchup.py prompt/map-reduce (pure, injected completion)
- catch-me-up-settings: EXTEND moreSettings (model + standing grants) and editPerson sheet (turn off); REUSE jumpTo for bullet taps
