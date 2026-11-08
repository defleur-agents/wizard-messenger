# Catch me up: model bake-off, one page (6 Nov 2026)

**Winner: `glm-5-3`** (reasoning_effort=low). Mean 98.3/100 vs 96.9 for `deepseek-v4-1-flash` run its best way
(thinking off). The gap is 1.4 points, above the rubric's 1.0 tie band, so speed did not decide it.
Both stay selectable in Settings > Catch me up; glm-5-3 is the default.

Setup: 8 synthetic transcripts I wrote (invented names/events, no real chats): 8, 25, 40 (unanswered question), 60 (mixed
Thai/English/Spanish), 100 (project, decisions, @mention of the owner), 300 (multi-topic), 1000 in one pass, 1000 forced
into map-reduce (small parts). Same prompt, input, 6000-token cap, temperature 0.2, timeout 170 s, two repeats per cell.
Rubric (RUBRIC.md) and deterministic scorer (score.py) fixed before reading results: coverage 30, owner asks 20,
faithfulness 20, source links 10, brevity 10, latency 10. No model judged any output.

| | glm-5-3 | deepseek-v4-1-flash, thinking off | deepseek, reasoning low | deepseek, defaults |
|---|---|---|---|---|
| Mean score | **98.3** | 96.9 | 91.3 | 72.8 |
| Mean seconds per run | 4.6 | **2.5** | 17.3 | 18.7 |
| Succeeded | 32/32 | 32/32 | 15/16 | 12/16 |
| Replies cut off at the token cap | 0 | 0 | 1 | 2 |
| 1000 msgs, one pass / map-reduce ok | 4/4, 4/4 | 4/4, 4/4 | 2/2, 1/2 | 1/2, 0/2 |
| Map-reduce score on 1000 msgs | **99.8** | 89.8 | 48.9 | 0.0 |
| Invented facts | 0 | 0 | 0 | 0 |

Findings
- deepseek-v4-1-flash with its default settings spends the whole token cap thinking and returns nothing on long chats
  (empty at 300 and 1000 messages, fails both map-reduce runs). With thinking switched off it is fast and reliable.
- glm-5-3 needs `reasoning_effort=low` or it also burns its cap thinking; with it, it never failed and covered the most
  planted facts, especially when 1000 messages are merged from parts (99.8 vs 89.8).
- Faithfulness was clean for all (no ungrounded names or numbers). deepseek-nothink twice reported a superseded fact as current
  (the old cabin price once, the old venue once); glm-5-3 never did.
- Both models recommended in-app: glm-5-3 default; deepseek-v4-1-flash (thinking off) is the faster alternative.
Caveats: synthetic chats, two repeats, one scorer written by me; not a quality test on real conversations.
Files: report.md (every cell, misses, raw outputs), scores.json, results-run{1,2,3}.json, corpus/.
