# Catch me up bake-off: rubric (fixed 6 Nov 2026, BEFORE any model run)

Models: Tinfoil `deepseek-v4-1-flash` (no extra reasoning params, per the 400 note) and `glm-5-3`
(`chat_template_kwargs.reasoning_effort=low`, else reasoning eats the cap). Same system prompt, same user
payload, same max_tokens (6000), temperature 0.2, 2 repeats per cell, 170 s timeout.
Data: synthetic transcripts authored by us (corpus.py); planted facts/traps/owner asks are listed with their
source message numbers in the corpus file, so scoring needs no judge model (a judge would be one of the contenders).

Score per run, 100 points (a failed or empty run scores 0 on everything):

| # | Dimension | Pts | How it is measured (deterministic) |
|---|-----------|-----|-----------------------------------|
| 1 | Coverage of planted facts and decisions | 30 | fraction of planted `fact`/`decision` items whose required regex groups all match in one bullet |
| 2 | Actionable asks surfaced | 20 | fraction of planted `owner_ask` and `open_question` items matched; an owner ask must be in a `for_you` bullet, an open question in a `question` bullet |
| 3 | Faithfulness (no invention) | 20 | 20 minus 7 per asserted trap (superseded value, rumour, prompt-injection claim; a trap is excused when the same bullet carries its `allow` words), minus 1 per ungrounded number/capitalised name (a token in the summary absent from the transcript text, up to 6) , floor 0 |
| 4 | Source links | 10 | fraction of matched planted items whose bullet `refs` include a true source message number; also 0 for refs outside the transcript |
| 5 | Brevity / readability | 10 | valid JSON in the schema (4); no preamble or fences needed (1); word total within budget: <=220 words for <=100 msgs, <=320 for <=300, <=450 above (3); every bullet <=40 words (2) |
| 6 | Latency | 10 | wall seconds for the cell: <=15 s full, linear to 0 at 120 s (map-reduce cells use the total) |

Reported separately, not scored: success rate (runs that returned parseable non-empty bullets / runs), whether either
model fails or empties at 1000 messages, tokens, bullets per run.

Winner = higher mean total over all cells. Tie (within 1.0 point) => the faster model on mean latency.
A model that fails (non-parseable or empty) on the 1000-message transcript in either mode cannot be the default
unless the other also fails.

## Addendum (written after run 1, before runs 2-3)

Run 1 used the fixed configs above. deepseek-v4-1-flash with no reasoning params spent the whole 6000-token cap on
reasoning and returned an empty reply (finish_reason=length) in several cells, including both attempts the app makes
(2 tries per call). Two extra deepseek configurations were therefore run with everything else identical:
`deepseek-v4-1-flash+nothink` (`chat_template_kwargs.thinking=false`) and `deepseek-v4-1-flash+low`
(`reasoning_effort=low, thinking=true`). Run 1 results stay in the tables unchanged. The default is decided on the
best-working configuration of each model (the one that would ship), and the summary says which configuration that is.
No rubric weight or scoring code was changed after seeing results.

Scorer fix (also before any winner was read): the capitalised-name check treated "Luigi" as ungrounded because the
transcript only contained "Luigi's"; possessives are now stripped. This affected both models equally (3-4 tokens per casual25 cell).
