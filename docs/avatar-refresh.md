# Preserve decoded avatars during refresh

## Reuse

REUSE Messenger's existing `pictureURL`, lazy observer and four-request avatar queue; the existing `drawList`/thread builders and Wizard Appearance fixture. No shared shell avatar implementation is used by this UI.
EXTEND `withPicture` with a bounded, memory-only cache of the actual image node per surface slot and URL. A refresh moves the decoded node synchronously, without assigning `src` again. List, thread-header, directory and group-message slots do not steal each other's images. Missing photos keep initials; real errors remain hidden and use the existing one-retry policy. A changed version URL gets a new image.
NEW regression cases only: browser-free state assertions and synthetic hosted phone/desktop, Nebula/Signal frame sampling. No installed Messenger data, contacts, messages or real images are read.

## Verification

`nice -n 19 node --test tests/avatar_refresh.test.cjs` checks ten refreshes, simultaneous slots, version changes, no-photo fallback, errors, cache bounds and browser harness syntax.

Queue `python3 tests/run_avatar_refresh_forum.py` on forum/light after staging `baseline-static` from the PR base and `shell-source` from Wizard's source `web` directory. The harness runs the real app with intercepted synthetic API routes, forces twenty list and twenty thread rebuilds per width across two real hosted skins, and records every animation frame after initial image load. Red must have a real initials-frame violation and green must have none, no image replacements, no JS errors, and no unknown API prerequisites. Screenshots are synthetic only; not evidence of an installed-origin run.

## Release coordination

This PR does not deploy or restart Messenger. The owning release thread must rebase it onto its reconciled default branch, rerun exact-head tests, and sequence the release. The live view currently pins `app.js`, `app.css`, and `index.html` to `dee754a` while unified assets come from the installed image; retain this distinction during release.
