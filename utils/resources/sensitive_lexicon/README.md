# Sensitive lexicon snapshot

This directory vendors the two political-content lists used by the bot's local
text moderation fallback.

- Upstream: https://github.com/konsheng/Sensitive-lexicon
- Pinned commit: `5a8da94c61c160e203a6b2fcfafbea642404d50c`
- Retrieved: 2026-07-30
- Files: `Vocabulary/政治类型.txt` and `Vocabulary/反动词库.txt`
- License: MIT; reproduced in `LICENSE`.

The local policy is only a deterministic pre-send safeguard.  It does not
replace platform policy updates or human review.  New terms must be reviewed
for false positives before they are added.
