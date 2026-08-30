# AIRA Stage 9 Step 4-6 — Runtime, Price, and Budget Review

Review status: HUMAN APPROVAL REQUIRED  
Generated: 2026-08-30 (Asia/Seoul)  
This file does not execute any provider request.

## Why this review exists

Stage 9 will measure the existing single-agent baseline before Stage 10 tests multi-agent behavior. The model, price assumptions, and hard ceilings must therefore be fixed before the first paid run. Changing them after seeing development results requires a new versioned manifest.

## Recommended runtime candidate

- [x] APPROVE — use this candidate
- [ ] MODIFY — record changes below
- [ ] HOLD — do not create a live manifest

| Role | Model | Reasoning setting | Why |
|---|---|---|---|
| planner | `gpt-5.6-terra` | `low` | Matches the existing planner's explicit low-reasoning configuration while using the current balanced model. |
| grounded answer generator | `gpt-5.6-terra` | provider default (`None` in the adapter) | The current adapter does not expose a reasoning-effort field; inventing one would make the manifest disagree with runtime. |
| citation evaluator | `gpt-5.6-terra` | provider default (`None` in the adapter) | Same adapter boundary; all three roles use one model to reduce an avoidable experimental variable. |

Recommendation: **APPROVE**, subject to a zero-call preflight immediately before execution.

### Why not the dated GPT-5 snapshots?

The official model pages list `gpt-5-2025-08-07` and `gpt-5-mini-2025-08-07` as deprecated. A dated identifier is attractive for reproducibility, but deliberately starting a new evaluation on a deprecated snapshot is not a sound baseline.

### Alias reproducibility boundary

`gpt-5.6-terra` currently has no distinct dated snapshot on its model page. Therefore the run must preserve:

1. the locked manifest and its SHA-256;
2. the price observation date and official source URL;
3. the actual model identifier returned by every response;
4. the prompt/configuration hashes and code commit;
5. a fresh zero-call preflight on the execution date.

If the documented model or price changes before execution, stop and issue a new manifest version. Do not silently edit the locked manifest.

## Price entries to approve

Observed from the official GPT-5.6 Terra model page on 2026-08-30. Units are USD per 1,000,000 text tokens.

| Usage | Price (USD) | Authority |
|---|---:|---|
| input | 2.00 | current documented price, not an invoice |
| cached input | 0.20 | current documented price, not guaranteed cache savings |
| output | 12.00 | current documented price, not an invoice |

Official source: https://developers.openai.com/api/docs/models/gpt-5.6-terra

These entries estimate cost from recorded usage. They are neither provider-reported billed cost nor an invoice. Tool-call charges are excluded; consequently paid tools must remain disabled for this baseline.

## Proposed hard ceilings

### Development phase — 4 disclosed development cases, one repetition each

| Ceiling | Value |
|---|---:|
| provider requests | 16 |
| all external requests | 24 |
| recorded tokens | 120,000 |
| elapsed time | 2,880 seconds |
| estimated monetary cost | USD 1.50 |

Run cases sequentially. Stop immediately on a ceiling, configuration mismatch, unpriced operation, missing usage, or malformed artifact. Review the four-case result before any holdout execution.

### Complete baseline — 10 cases total, one repetition each

| Ceiling | Value |
|---|---:|
| provider requests | 40 |
| all external requests | 60 |
| recorded tokens | 300,000 |
| elapsed time | 7,200 seconds |
| estimated monetary cost | USD 4.00 |

The monetary ceilings are hard upper bounds, not spending targets. They cannot increase automatically. The USD 4.00 ceiling is slightly above the conservative all-output-token bound of USD 3.60 for 300,000 Terra tokens; real cost should be lower because input tokens are cheaper.

## Experimental rules

- Development cases: 4; tuning and debugging are allowed only here.
- Blind holdout cases: 6; do not inspect their expected answers or tune after starting them.
- Repetitions: 1 per case for the essential baseline.
- Paid web search and other separately priced tools: disabled.
- Retry: only a bounded transport retry already declared in the manifest; no manual unrecorded retry.
- Any prompt, rubric, model, reasoning, price, budget, or code change after lock requires a new manifest version.
- Stage 10 must use the same locked dataset and comparable ceilings; otherwise its single-agent versus multi-agent comparison is not valid.

## Human approval checklist

- [x] I verified the official model page on the execution date.
- [x] I accept the absence of a dated Terra snapshot and the compensating audit records.
- [x] I approve the three runtime role mappings above.
- [x] I approve the development ceilings.
- [x] I approve the complete-baseline ceilings.
- [x] I understand that documented/estimated cost is not billed cost.
- [x] I understand that approval creates no API request; a later explicit command performs the paid run.

Reviewer ID: moon
Reviewed at (timezone required): 2026-08-30T09:21:35+09:00
Decision reason: Approved the current Terra runtime mapping and conservative hard ceilings for the single-agent baseline.
Requested modifications: None
Unresolved issues: Terra has no dated snapshot; preserve actual response model IDs and stop if model or price documentation changes before execution.
