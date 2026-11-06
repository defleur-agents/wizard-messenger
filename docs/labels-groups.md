# Labels: your own groups of chats (0.2.0-unified.16.26)

James's ask (6 Nov 2026): a group in Messenger he can add chats to, across all channels, e.g. one for WizardOS.
It is the existing Labels feature, extended:

- A label is a name in the persisted catalogue (`label_catalog`, created with `CREATE TABLE IF NOT EXISTS`; existing `room_label` rows are folded in on first start, so nothing existing changes). It exists while empty.
- `WizardOS` is created once on upgrade (kv flag `label_seed_v1`): if James deletes it, it never comes back.
- Any chat can carry labels: people, groups and merged people (applied to every identity so the person aggregation works). POST `/api/unified/people/<id>/labels`; the older `groups/<identity>/labels` route still works and now accepts any identity.
- Owner-session routes only: GET/POST `/api/unified/labels`, POST `labels/rename`, `labels/delete`. None maps to an agent capability, so the machine key and agent keys get 403 (`agent_access_off` when access is off).
- Rename onto an existing name merges the two; delete removes the label from its chats and never touches the chats.
- UI: chat info sheet > Labels (checkboxes + New label), row hold/right-click and thread menu > Labels, Filters strip > Labels… (Manage labels), label chip shows chats from every network, an empty label says how to add chats.

Adding a chat: open the chat, tap its name, under Labels tick WizardOS (or hold the chat in the list > Labels).

Tests: tests/test_unified.py (PeopleTests label cases), tests/test_agent_permissions.py (machine key 403), tests/labels_browser.cjs (phone+desktop, dark+light, synthetic API only).
