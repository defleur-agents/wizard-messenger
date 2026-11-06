# Inbox view: Chats or Compact (0.2.0-unified.16.27)

James (6 Nov 2026): the 16.x list had no message preview line, which broke the chat feel.

Cause: 15.12 (the Miguel list-and-detail release on the shared 16.x line) made the compact row the default and put previews behind Settings > "Message previews in the list" (off). The 15.15.1 line James had been using never had that switch: its rows always showed the last message.

Now: Settings > Inbox view, saved at once on this device (localStorage `messenger.inboxView`).
- Chats (default): picture, name, last message (a group names the sender, your own reads "You:"), time, unread badge. The row code is the same one 15.15.1 used; tests/inbox_view_browser.cjs dumps the rows and `STATIC_ROOT=<15.15.1 static>` produces the 15.15.1 rows to diff.
- Compact: the 16.x denser row (name, time, badge).
One renderer in unified.js drawList(); the old `messenger.previews` key is no longer read.
