# Default/release-line reconciliation (6 November 2026)

## Why the histories diverged

The default branch was `feature/unified-inbox`; on 6 Nov 2026 it was renamed to `main`, the single trunk (no side trunks, no Alpha channel). The live composed repair line was pinned to the 15.14 source/base image (`4566306576d3a6805da1ba531da3a89214dfd7af`) so only Messenger and Signal changed during an owner-specific, data-preserving lifecycle operation. See `docs/composed-release.md`, `docs/account-attachment-release.md`, `REPAIR-HANDOFF.md`, and PRs #100/#102/#103/#106/#108. It deliberately did **not** replace init, translation, healthy workers or the owner's settings. This was a narrow deployment constraint, not a decision to discard later product work. Keeping that older line as the permanent release source accidentally separated it from the public Store source.

The composed release branch has 8 commits not on default; default has **132** commits not on that branch. The mention branch adds LINE and group work and inherited this same old base. The 132 commits are real app development, not just release metadata: keyboard shortcuts and app-key fallback; owner/agent permissions and in-chat drafts; group search/labels and labels editor; cached thread/instant-open behavior; member/mention display names; photos/media/waveforms; compact previews; unread dividers and follow/park behavior; opaque settings sheets; immutable public multiarch images and consolidated all-worker Store recipe; null-prototype caches; input/paste/jump fixes; lifecycle safety and verification. The exact full list is below.

## Integration rules

- **REUSE** the existing `UnifiedInbox`, `PeopleStore`, connector pending-login controller, existing `WizardApp`/Appearance v1 skin loader and shared keys. **EXTEND** those paths with group mention spans/member backfill and reactor identities. **NEW** only source-test orchestration/CI; no second messaging, membership, permission or appearance service.
- Merge both histories, not a squash/cherry-pick of a few visible files. Preserve default's keyboard, agent, draft, media, follow/park and translation behavior while adding the live repairs.
- Preserve the public digest-pinned, consolidated recipe. Its LINE service already has the installed marker-watching worker required by #113. Do not restore the retired optional connectors overlay, developer-local image tags or `pull_policy: never` for public registry images. #113's regression now checks the actual shipping recipe instead of the retired overlay.
- Merge #115's `private_data: true` declaration and #117's Instagram controller fixes as well as #109/#112/#113 and notice removal #108. Do not mutate or force-push their authors' branches.
- Keep default's `0.2.0-unified.16.24` version, not a downgrade to `15.16`. The release owner should bump **all** version sites together to a new monotonic version (e.g. `0.2.0-unified.16.25`, after checking intervening releases). “15.16” is only the pending repair batch's old name, not a reason to revert 132 commits.
- All future release branches start at the merged default commit. Existing helper branches remain untouched. Merge/rebase new helper commits onto that default with normal PRs; never resume cutting from the composed branch.

## Verification and release boundary

`uv run --no-project --with-requirements tests/requirements-unit.txt python tools/check_source_tests.py` runs the full source-only Python suites (main, isolated sender, push, readiness) and browser-free Node suites. Synthetic fixture updates preserve the historical 15.14 recipe separately, provide explicit keyboard DOM APIs, and migrate permission tests to current Settings/Advanced/in-chat draft contracts; they do not restore obsolete UI.

Browser/layout/two-skin proof and real provider login/round trips remain separate gates. A source-only `app-parity-gate` comparison from parent-identified live `603039eb` finds **zero missing routes, modules or tests**, but its label heuristic blocks nine labels: Direct/Groups/Merged/Unread are still literal choices in `TYPES`/`SEGMENTS`; low-priority commands are now under the three-level Priority menu, and success text is held in a computed `said` variable. This is **not a gate PASS or a waiver**: the release owner must resolve the label inventory with behavior-linked evidence before cutover. See `tests/filter_layout_browser.cjs`, `tests/inbox_tweaks_browser.cjs` and `tests/test_unified.py` for the retained filter/priority behavior. This reconciliation never reads Messenger owner data, databases, environments, logs or containers, and never installs or restarts an app. No Alpha catalog or GitHub release publication is authorized by this merge.

## Exact 132 default-only commits

- `97047668c24b22b3fac2f5f52a9cca9055eb7dc4` Merge pull request #111 from humanitylabs-org/release/pin-16.24
- `d26d5ca4b8c0ca6cc73893524f2e309bf01ff64e` Store recipe 0.2.0-unified.16.24: pin Messenger sha-172f85e (#110)
- `172f85e9065d2cab2e056bfb6b1009f34fe66155` Merge pull request #110 from humanitylabs-org/feat/unread-divider
- `b5d43de2d90d04ffe7a5a9861506cac8d8f72d37` incoming_media_browser: read down to the bottom before the off-screen GIF check (chats now open at the first unread)
- `d4e3ef9797d6a143d1cb54e3abb86616f5dc9919` Messenger 0.2.0-unified.16.24: 'N new messages' divider and open at the first unread
- `f1bb7a130abc447e7beaabb8243801ac8d2f64e1` Merge pull request #105 from humanitylabs-org/release/pin-16.23
- `e865875f8be38a4104daf7634fab3230badedbbf` Store recipe 0.2.0-unified.16.23: pin Messenger sha-e199ae8 (#104)
- `e199ae8ed61089d9aabff1baa4cb4dd162f29e38` Merge pull request #104 from humanitylabs-org/fix/whatsapp-status-label
- `279c1acae09579d2af9d9a252df627750e4694d9` Messenger 0.2.0-unified.16.23
- `0d90351d1bd4dd0ca28e59a6863e38ca7b5d289a` WhatsApp Status Broadcast: label undecryptable status posts as a status update to view on the phone
- `3926839cbddca38ffc171d81fc9e2a6dd4355c66` Merge pull request #101 from humanitylabs-org/release/pin-16.22
- `dadb16090ad7babadb4f317a5438b5bfe7349c0e` Store recipe 0.2.0-unified.16.22: pin Messenger + Telegram bridge sha-6ab2ed0 (#99)
- `6ab2ed06c48787acb22828b6296597f6f1dfe1a7` Merge pull request #99 from humanitylabs-org/feat/composer-pickers
- `606a7c0aef4f4ed712478f569fd75eea8d18fd20` pickers: rem type for emoji glyphs (style ratchet)
- `c89fbb79f6a44d0b998907ede2f3c808aa9f6810` Messenger 0.2.0-unified.16.22: Emoji / GIFs / Stickers picker in the composer — shared Wizard emoji at the caret with Recent; the owner's saved Telegram GIFs + @gif search sent as Telegram GIFs; recent/favourite stickers and installed packs sent as the original Telegram sticker (bridge pickers.patch)
- `acc3f2f825242281126ab8916190c41605ec6131` Merge pull request #98 from humanitylabs-org/release/pin-16.21
- `a0d370feb281e21917a64c96c5a59c933a19f7ca` Store recipe 0.2.0-unified.16.21: pin Messenger sha-ce1ad8f (#97)
- `ce1ad8f3729d489fa7f6be59aa77ad368a5db319` Merge pull request #97 from humanitylabs-org/fix/react-media
- `d3400af1a0e5c1fe08e87bec6f04be33725e9ade` Messenger 0.2.0-unified.16.21: react to GIFs, stickers and photos — right-click or long-press on bubble-less media opens the message menu with reactions (tap still opens the viewer / plays a held GIF); react_media_browser covers it
- `e9c6efed3e1b2d3169e1d8f0ba41819268c01aee` Merge pull request #96 from humanitylabs-org/release/pin-16.20
- `139ad9320990171a48e5068090871ebbc80a4fe9` Store recipe 0.2.0-unified.16.20: pin Messenger sha-e5c4550
- `e5c4550f3dcc1a570f73e9d62303727876115b0c` Merge pull request #95 from humanitylabs-org/fix/wkwebview-confirm
- `a88b0a1c6705bba0528b4515135edd5ddbba1c8c` Rerun reuse check
- `22352d79b6b890407c3d10ff881b33656201437c` Delete for everyone works in the Mac app: in-app confirm instead of window.confirm (16.20)
- `2b3fd4ebdc2963bc0a1533162d882b39d314f2f5` Merge pull request #94 from humanitylabs-org/release/pin-16.19
- `70b8a61e828a2725a61a4000f47c0bf49a78af6c` Store recipe 0.2.0-unified.16.19: pin Messenger sha-5f0de12 (#93)
- `5f0de12f4df1509ce9d20dd8a8a848060185c4b9` Merge pull request #93 from humanitylabs-org/fix/edit-sender-mxid
- `bc038bf10959b9d7c244384116160e87b940e9ba` Messenger 0.2.0-unified.16.19: edits are settled by the author's mxid, not the stored display name (WhatsApp ghost renames dropped decrypt-retry photos); repair_waiting_v2 reapplies them; never-resent decrypt failures older than 1 h read "Message couldn't be decrypted"
- `7029085634a5db4264588f53ae396abb75572dc4` Merge pull request #92 from humanitylabs-org/release/pin-16.18
- `56566e3fe7236eac7f78445138416b0e907fb5f8` Store recipe 0.2.0-unified.16.18: pin Messenger sha-f7a910e (#91)
- `f7a910ee432dfa2f2909997b2a9fc2fc4cc09447` Merge pull request #91 from humanitylabs-org/fix/alt-anchor-keys
- `60be0bf41b53cbfafa67ec937ff224a0776d939d` Messenger 0.2.0-unified.16.18: one anchor — data-wz-key means ⌥+key; the fallback acts only on ⌥+key by e.code in a standalone tab without WizardApp.keys (plain keys never act, no repeat, framed inert); app_keys_browser covers it
- `88e14bd883426a7c5fbc45aafd1aa442e7ab3e2c` Merge pull request #90 from humanitylabs-org/release/pin-16.17
- `44eb20adca94316be49c9f99aaf2bd9fd80422bf` Store recipe 0.2.0-unified.16.17: pin Messenger sha-ea96bbe (#89)
- `ea96bbee49800c6050bfdecaedb9747023f17833` Merge pull request #89 from humanitylabs-org/fix/visible-keycaps
- `880bedfc5fe9c9919fe8ce4d4086b7d0472ce9bb` Messenger 0.2.0-unified.16.17: keycaps sit on what the key does (j/k on chat rows or the ↑/↓ chat-header buttons, r on the reply box, / on Search); app_keys_browser covers it
- `43d6d45103b2ac405c9b8f01af9fdb403746c874` Keys: keycaps sit on what the key does (j/k on the next/previous chat row, ↑/↓ chat-header buttons when no list is beside the chat and a keyboard is present, r on the reply box, / on the visible Search); the quiet row keeps a key only while its target is off screen
- `12543712134f1e709b75d47aea01cf5579fe54d1` Merge pull request #88 from humanitylabs-org/release/pin-16.16
- `b94e9308c820f32a3cac64a4a8c82c02253da14e` Store recipe 0.2.0-unified.16.16: pin Messenger sha-2ebb0fb (#87)
- `2ebb0fb7d3a320c676fdc23d68fa1d04651e2e00` Merge pull request #87 from humanitylabs-org/fix/incoming-media-gif-mentions
- `de30adc8171c0fd95e6b81af521580be60c8981b` Re-run reuse check
- `4cc88630f63d09e6df165b9dee8de1317a9adc4a` Messenger 0.2.0-unified.16.16: show photos/GIFs behind WhatsApp decrypt retries, play GIFs and animated stickers, readable @mentions, expired-media placeholders
- `8eaf6fbf0a6b59f61614bd5792611688bd0f761c` Merge pull request #86 from humanitylabs-org/release/pin-16.15
- `b504245435f883ac8d7acbc44c982945b1663f7e` Store recipe 0.2.0-unified.16.15: pin Messenger sha-ad5c786 (#85)
- `ad5c786eb16f8cc3246630d334551eecc9f4db3a` Merge pull request #85 from humanitylabs-org/feat/app-keys-16.15
- `bd7a6bda589e2924ffe5a175ec6e4297a9161e45` Messenger 16.15: keyboard shortcuts via the Wizard app-key contract (j/k next/previous chat, r reply, / search, n new chat)
- `135bfb1e90f5dab8d340f504091e1ded1635b45e` Merge pull request #84 from humanitylabs-org/release/pin-16.14
- `5d56fff783a3f04d31b77bc621d60c8c05e26849` Re-run reuse check
- `127821077cba1c0c8ce80d82933ff02769163260` Store recipe 0.2.0-unified.16.14: pin Messenger sha-c471366 (#83)
- `c471366705835f29ffbd2e069114653ff6c6e5d8` Merge pull request #83 from humanitylabs-org/ux/friendly-pass-16.14
- `17204d3c86fb0f91b02189c59812dd073908e1d0` Messenger 16.14: friendlier phone Inbox (44px touch filters, explained empty folders, Clear filters, clearer search, distinct menu icons, readable agent warning)
- `fd0c1fc9af0f65fc7916a10c7771c3370e0356a8` Merge pull request #82 from humanitylabs-org/release/pin-16.13
- `3b2417ec4c3a1ba45f45c39538a7b6c6bdb26b06` Store recipe 0.2.0-unified.16.13: pin Messenger sha-7a543c8 (#81)
- `7a543c86e3d7f2e7aa91f51ad6533b079ee735da` Merge pull request #81 from humanitylabs-org/fix/voice-original-recovery
- `46b07667b71c4e3cf7a78c7285330310422039d6` Voice archive: roll oldest takes out of the 250 MB budget instead of failing every later voice note
- `ab1102849e606e1cf50f29f9eb1df515bc5f4d1a` Resolve recovery identifiers only against private archive directory entries
- `bb0c17ece5aef42e61dfb4dd3077b730d43c0554` Validate archive entry basenames at the descriptor read boundary
- `637963cb4609f929737f089c432bcf1024ecb4ef` Messenger 16.13: privately preserve original voice bytes and offer raw recovery export
- `5afdd5e2d92e0f024604ff04740623caf90c9f69` Merge pull request #80 from humanitylabs-org/release/pin-16.12
- `fb7960f75449a28c4b78116d9a59e4bb4f522271` Store recipe 0.2.0-unified.16.12: pin Messenger sha-d4a0959 (#78, #79)
- `d4a09598a0b578954c8a3d33ac30e55e060c4b19` Merge pull request #79 from humanitylabs-org/fix/voice-webm-server
- `690a9fc376a6d698c973c5ceb6c2c5c9306da575` Messenger 0.2.0-unified.16.12: Mac app voice notes record with Safari's own WebM recorder (keeps recording when Wizard is hidden; Web Audio PCM stops, WebKit 231105, which clipped a 2-minute note to 7 s); WebM the browser cannot rewrap is rewrapped to Ogg Opus on the server with mkvextract; the server measures every Ogg voice note and refuses one shorter than its recording (voice_clipped) and sends the real duration
- `32a9843a6745f715f45013e7818275ecb8a793cc` Merge pull request #78 from humanitylabs-org/fix/voice-capture-guard
- `a78600295f45675c44d5ccc91be05d8b9c2f6b00` Messenger 0.2.0-unified.16.11: never send a clipped voice note. Plain-audio takes are checked against the recording clock: a stalled microphone shows a notice while recording, and a take missing more than 3 s / 10% is kept as an unsent voice note (Send still possible) with how much was captured and whether Wizard was hidden or behind another app. Test: tests/voice_capture_guard_browser.cjs
- `60125bd82f3c6db30b7e5b3fbde9f05147d6abc9` Merge pull request #77 from humanitylabs-org/release/pin-16.10
- `7843205452e12418e0333381772d187bda257b40` Store recipe 0.2.0-unified.16.10: pin Messenger sha-6370c5f (#76)
- `6370c5f2e391c1bcbe29aed71370489f964dd5f3` Merge pull request #76 from humanitylabs-org/fix/voice-server-opus
- `313c6bad8bb6551682d87d2fc2e6610976e526e4` Messenger 0.2.0-unified.16.10: Mac app voice notes record plain PCM WAV through the shared recorder (pcm mode) and the server encodes them to Ogg Opus with opusenc (opus-tools added); Safari's fragmented MP4 lost its header on long takes ((moof) error). Tests: tests/test_voice_wav.py, voice_m4a_fallback_browser WAV case
- `e738d3dd694e877a6d9ed91dafc193a70c6dbc02` Merge pull request #75 from humanitylabs-org/release/pin-16.9
- `a9e1fb4a9575a75fac8e858075f41d5cc37f4d8f` Store recipe 0.2.0-unified.16.9: pin Messenger sha-c489166 (Mac app voice notes, #74)
- `c4891661b442e599cf6bc33d03bb19ab4b50aaa9` Merge pull request #74 from humanitylabs-org/fix/voice-safari-webm
- `4d9c0fbf32437de6056f2e5a7fac351a25d91550` Drop the MediaRecorder re-record fallback (shared capture owns recording); new Mac takes are M4A
- `737a840ab5c22ac4846a6b4caa8ce365edf3e019` Messenger 0.2.0-unified.16.9: Telegram voice notes from the Mac app. Without WebCodecs AudioEncoder, record M4A (sent as is); a take that is neither Ogg nor M4A (Safari WebM, raw AAC) is played once into the browser's M4A recorder instead of failing; WebM rewrap keeps whole packets from a cut-off file; the error names the format
- `a1cf9ef24f0eec8a5aaf7ff00b8cbfcc2ae6b2a7` Merge pull request #73 from humanitylabs-org/release/pin-16.8
- `9e22383917f94176f52c52ff11b93e595a3d8ec3` Store recipe 0.2.0-unified.16.8: pin Messenger sha-8260f0f (Telegram voice notes as M4A from Safari/Mac app, #72)
- `8260f0f5a7458a819ae43a2731ce66e8a3a12bc7` Merge pull request #72 from humanitylabs-org/fix/voice-m4a-fallback
- `838878852750d53a406e81f09f293a989e778c99` ci: rerun reuse check
- `354f76a20208d30bcd1974b6dfba2e1181065493` Messenger 0.2.0-unified.16.8: Telegram voice notes from Safari/Mac app (no WebCodecs AudioEncoder) are sent as M4A, which Telegram plays as a voice note, instead of failing with "This device cannot prepare voice notes for Telegram yet"; also falls back to M4A when the Opus re-encode fails. Test: tests/voice_m4a_fallback_browser.cjs
- `65c7666604155ad4b7a59b9a48fd48f8dae1b551` docs: list user-facing Messenger under Apps (#71)
- `ac5a0250d3d0429c2e9d674da3105333fe7bac9e` docs: separate public Messenger install from historical beta (#70)
- `90b3134b4cac079cc60c02d902cfed5a81065ed8` Merge pull request #69 from humanitylabs-org/release/pin-16.7
- `33d34aac6ab099d53b96b03321f1cb13baf3fba6` Store recipe 0.2.0-unified.16.7: pin Messenger sha-40ee0c6 (owner Unix hop fix, #68)
- `40ee0c6fef1645a0aed5fc24494c1832e32460b3` Merge pull request #68 from humanitylabs-org/fix/owner-hop-index
- `3dfc8bc8dac290d383992d0cf3a80070a5530b78` Messenger 0.2.0-unified.16.7: the page loads through the owner Unix hop again (16.5/16.6 regression)
- `842de825ca24c8b5b9eecf593a42b53694190ab2` Merge pull request #67 from humanitylabs-org/release/pin-16.6
- `7615fae766d238ff528db36f47d6c21215f74934` Store recipe 0.2.0-unified.16.6: pin the Messenger image sha-c2bfb7d (raw-port redirect runs before the WizardApp check, #66); Telegram and bridges unchanged
- `c2bfb7db87bcdbe4dec88e4b886a0c1ca6848699` Merge pull request #66 from humanitylabs-org/fix/raw-port-redirect-early
- `f8c92ccbd8bfe8fa6da309d4d6e9fbe195c1a0b9` Messenger 0.2.0-unified.16.6: the raw-port redirect runs before the WizardApp check
- `6da59cff9894b7d2614ea4d6f0b4b87977f1557e` Merge pull request #65 from humanitylabs-org/release/pin-16.5
- `a8f81d71e47ad38268a321ddef4cf3c29c66d69f` Store recipe 0.2.0-unified.16.5: pin the Messenger image sha-3eb0b98 (raw-port open recovers to the Wizard path, #64); Telegram and bridges unchanged
- `3eb0b9833b82efeb326fca076552ed385b13f8a2` Merge pull request #64 from humanitylabs-org/fix/raw-port-redirect
- `8a2eaf55e820dc25d5d77b33395d4b1a613598a5` tests: raw-port fixture proxy passes a fixed header allowlist without CR/LF (CodeQL on #64)
- `de335dbb8d546366ff107d1d7790752218e8fe9f` Messenger 0.2.0-unified.16.5: opened on the raw app port, Messenger moves to its Wizard path instead of a dead card
- `241c4f9b8b3b46d04f8602388f58bc7e93f63fae` Merge pull request #61 from humanitylabs-org/release/pin-16.3
- `54d6053bc2b3e28cf56b4ee34e522585d7e9514b` Store recipe 0.2.0-unified.16.3: pin the Messenger image sha-3d789e1 (chat list beside the open chat from 640px, #60); Telegram and bridges unchanged
- `3d789e1f85c9a5c78ebe313e0679bc9835a2d6f9` Merge pull request #60 from humanitylabs-org/miguel/split-narrow
- `343a0d8dad1cf3e522426e9552172280654a1025` tests: split_divider_send covers the 16.3 640px split (chat keeps 380px at 640/700; narrow send at 600)
- `ab7a8abc54394def47c84ec348409b2b689e102c` Messenger 0.2.0-unified.16.3: the desktop split (chat list beside the open chat) starts at 640px of Messenger's window instead of 900px, so a ~760px Wizard window shows both; list 260px+ and chat 380px+ (divider and CSS clamp), filter segments never clip in a narrow list pane, ✕/Escape close the chat back to the full-width list
- `a62835ab9693b315089b200a133a8fc2e1aa1b45` Merge pull request #59 from humanitylabs-org/release/pin-16.2
- `ec2ece7451b9ea2951e95daee421e83001bb4656` Store recipe 0.2.0-unified.16.2: pin the Messenger image sha-63deb42 (two-row Inbox filters + Medium priority, #58); Telegram and bridges unchanged
- `63deb42047819d62fc2ac1a0aef0cc795748401a` Merge pull request #58 from humanitylabs-org/miguel/filter-rows
- `a995af093417df408cdb6eabe1dbeb673a2d8d18` Messenger 0.2.0-unified.16.2: Inbox filters in two rows that never scroll sideways (All/Unread/Medium/Low segmented control; network icons + Filters menu with Type and Labels, overflow folds into +N) and Medium priority (stays in All, never pings: no push, badge, Unread count/view or Wizard inbox feed; exclusive with Low; Priority: Normal/Medium/Low in the row and thread menus)
- `4e6786663fae641e5eda1847847ae586f9fca401` Merge pull request #57 from humanitylabs-org/security/pyasn1-0.6.5-20261101
- `82ac30b0b46569d3668ab4c1ef9051aeb89e3e90` fix: update pyasn1 to 0.6.5
- `8ebdb896a942cdff558373583fe001a34c2d5c94` Merge pull request #56 from humanitylabs-org/release/pin-16.1
- `114475eeedd1211cd0dc76e8790e404f581a16ad` Store recipe 0.2.0-unified.16.1: pin the Messenger image sha-1ff7301 (legacy gateway key, #55); Telegram and bridges unchanged
- `1ff730181cb6dd158edcce41b90ac181c8e4e59d` Merge pull request #55 from humanitylabs-org/fix/legacy-gateway-key
- `14cfe517c8c2352ce265936e4559cfced243b418` Messenger 0.2.0-unified.16.1: Wizard agents keep their Messenger tools on boxes whose Agent Service predates app grants (the per-app gateway key is honoured again, only where the operator provisioned MESSENGER_GATEWAY_KEY_FILE; same MCP-only, per-agent-level rules as the grant)
- `fcb42d7166aff8c12c9aadf19265761292929592` Merge pull request #54 from humanitylabs-org/release/store-connectors
- `fdff7273c3f50984117a08da5b531955d902de3d` Store recipe 0.2.0-unified.16.0: every connector bridge in runtipi/docker-compose.yml with public digest-pinned images (Messenger + Telegram sha-9217753, LINE and ChatGPT Dots built by bridges.yml); bridges wait for their configured marker; init jobs excluded from Runtipi status; connectors.compose.yml retired
- `9217753b7699ec3f259b00cdc56c79c63f61cc5f` Merge pull request #53 from humanitylabs-org/feat/box-features-to-store
- `1e2d1ac7b9165c75a4e833c66f9c5260a04e59c8` Test: open a chat before measuring the divider (15.12 list and detail shows no divider with nothing open)
- `ce3cfceafb90e496bb098ad5d43717fa3e45ca63` Messenger 0.2.0-unified.16.0: bring the box-only 15.12 features into the Store branch (inbox feed instant change signal + api/inbox/wait long poll 9b801d5; list and detail layout, compact list default, Settings > Message previews 51f838c/161edfb); CI publishes the LINE and ChatGPT Dots bridges as public multi-arch images
- `ccb1e4e049263467bd75d99c258f8180764bfbc3` Merge pull request #52 from humanitylabs-org/release/public-recipe
- `3ddedbd533acd52f829e89642475de5da1cc8d93` Store install: use the published multi-arch Messenger and Telegram bridge images
- `9cf82834488c520039eea59ce228b4276c489042` Merge pull request #51 from humanitylabs-org/fix/image-smoke-token
- `e8fe3ab9ad1ddf81daac461477f899432440f6c2` Image smoke: use a full-length random API token
- `dd58b0bae6c06bab462e47a66e54963193a7d91f` Merge pull request #50 from humanitylabs-org/fix/image-smoke
- `3092521c34cf3bb272a97c6c0f41282fdcd9fc84` Image smoke: check the engine with wn --version
- `e8ffaabf0d37e24be6751615445782c8fe928445` Merge pull request #49 from humanitylabs-org/release/public-images
- `63297f1164640a24a73183a6b293881b4ddf503b` Publish Messenger and Telegram bridge images from GitHub-hosted amd64/arm64 runners; source build carries the wnd leak fix
- `d364fe92179714bb98cfb046b44eeb599b1f6f4a` Merge pull request #48 from humanitylabs-org/feat/agent-attachments-store
- `1d3f03fd8072d9b00ecb6c8846bff1490b371c47` CI: re-run reuse check
- `31399511449bc41ff8695ac616d0623bc0a1cd0a` Messenger 0.2.0-unified.15.15: agents can see photos in chats (messenger_read_thread attachment references; Read-only messenger_get_attachment returns pictures as MCP image content through the view's media cache, <=1.5 MB)
- `77a21f949b743b8c7edfc7f35c0586ca8f723556` Merge pull request #46 from humanitylabs-org/fix/safe-thread-keys
- `cda9029e4279ab9130a4dada410f534da05577c4` Merge pull request #47 from humanitylabs-org/security/rustls-0.23.46-20261031
- `562a0b78f6db3c4492d4dde7289c8656e91251c7` Maintenance: upgrade rustls to 0.23.46
- `44d17d916274478478bba6e3b5aa39fec952c0de` fix: keep reserved chat IDs out of inherited thread state
- `850c3b1a156b7b8502e5f87148cc4f918e5c93ed` Messenger 15.13: unify live fixes and Wizard linked-device names (#39)
- `161edfba28bf27f5a594794407266a662faf8a77` Messenger 0.2.0-unified.15.12: version
- `51f838cfb012c72e913de30af31b4753784eeb22` Messenger 0.2.0-unified.15.12: list and detail (Miguel): with nothing open the chat list fills the window; a chat or New message opens beside it and ✕/Back/Escape close it back to the full list; narrow windows slide the chat over the list and Back keeps the list scroll; compact list by default (picture, name, time, unread count, no last line), Settings > Message previews in the list brings previews back on this device; full screen keeps the headers below Wizard's Exit pill
- `9b801d5eb5397dfc6c666d6f523e5499ff0d8f39` Wizard inbox feed: instant change signal (version + api/inbox/wait long poll on the view's own change condition)
