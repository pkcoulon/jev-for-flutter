# Focused reads: version 0.3 measurements

These figures describe version 0.3.0. Version 0.3.1 adds [parallel preparation](PREFETCH-RESULTS.md) without changing the selection questions; this campaign does not measure that change's effect on complete answers.

On September 29, 2026, three pairs of Claude Sonnet 5 sessions at medium effort evaluated the new read hook. **Cost falls across these three cases; total time increases.** Answer criteria, prompts, sources and spending caps were fixed before calls, with no retries.

| Total across three sessions | Without plugin | Jev for Flutter | Change |
|---|---:|---:|---:|
| Claude tokens, input/cache/output | 102,780 | 76,974 | **−25%** |
| Claude + Jev cost | $0.247752 | $0.145253 | **−41%** |
| Claude-reported runtime | 20.638 s | 24.786 s | **+20%** |
| Read calls | 3 | 3 | No extra calls |
| Fully accepted answers | 1/3 | 2/3 | Too few cases to estimate a rate |

Every run, including imperfect answers, is included. The token percentage covers **Claude**. Jev separately processed 40,954 input and 2,234 output tokens, costing $0.001720, already included above. The combined token volume increases: delegation uses more of the smaller model and less Claude.

![Focused read results](img/read-results-light.svg)

## Exact scope

Three questions about a specific function in a known file: notification actions in Gambade, sync-cache invalidation in Pioudex, and audio-tier promotion in Pioudex. Only Read is available in **both variants**, to isolate reading. The prompt neither names Jev nor requires a full read; all six sessions chose one Read without an explicit range.

The complete plugin uses default settings. Project copies have no memory or local rules. The router still made three requests, included in cost. Each variant receives the same file from the same commit. No source was modified.

Sources: Gambade `fcac6e853a1a1ff70fa56c2eb5ec08b17ac7f10c`, Pioudex `91036cc5a13a474a3743c56919b598919cd84500`. Plugin identity and file hashes are in the [data](read-results.json). Branding and help were finalized after freezing the snapshot; the selection algorithm and defaults match the tested version.

This does not evaluate open-ended repository search or a completed fix with tests. It targets the hook's intended situation: a localized question with an avoidable full read. Earlier development trials, including unfavorable results, remain in [CONTEXT-RESULTS.md](CONTEXT-RESULTS.md).

## Quality: source coverage and answers

| Case | Plugin range | Expected passage present | Answer without / with |
|---|---|---|---|
| Notification | 16–165 of 590 lines | Yes, complete method | Rejected / accepted |
| Caches | 466–616 of 755 lines | Yes, complete method | Rejected / rejected |
| Audio agreement | 304–453 of 453 lines | Yes, complete method | Accepted / accepted |

The notification control omits empty-payload handling, a predeclared criterion. Both cache answers reverse the order of identity updates and cache clearing in their prose, although the plugin answer quotes the correct code. Both audio-tier answers cover the `none` guard, agreement count, scale and cap.

The audio tier is the only pair with two fully accepted answers: **−19% Claude tokens, −33% cost and −11% runtime**, one run each. This subset was identified after review and is not used alone as the main chart.

Astra reviewed the answers in the same session, neither independently nor blind. No paid judge was used. Source presence does not guarantee answer correctness; these are separate checks. The omitted-line note was found in full in all three Claude transcripts, without externalized output.

## Fallbacks and checks

- 28 offline checks covering Read arguments, full-file recovery, concurrency, errors, changed source, exclusions, secrets, compatibility and search caps.
- Six extra real Jev requests: whole-file review, multiple behaviors, complete sync flow, audio/photo comparison, and two absent behaviors. **6/6 reads stayed unchanged**, costing $0.002812.
- Observed hook times for the three focused reads: 364, 400 and 412 ms. These are not Claude answer times.

Thresholds were not tuned on those six checks. They reduce omission risk without eliminating it. No general quality or speed improvement is established.

## Accounting, reproduction and budget

Cost is Claude's reported value, checked against deduplicated usage and cache categories, plus Jev input at $0.042 per million tokens, with free output. Runtime uses Claude's `duration_ms`; less precise process timings, affected by two-second polling, are also retained.

Variant order: without/with, with/without, without/with. One run per case, no variance estimate, personal settings or connected MCP tools. Generation, cache and API variation remain possible factors. This is a limited favorable case, not a guarantee for every user.

This campaign cost **$0.396**, including extra Jev checks. The conservative historical total at this stage was **$3.4341 of the authorized $5**. No paid process remained active.

Plan, pinned sources, Jev requests and private transcripts: `~/.cache/dartlens-bench/read-redesign-2026-09-29/`. Normalized answers, usage and criteria are in [read-results.json](read-results.json). Earlier campaigns are separate.

Charts calculate percentages from JSON:

```bash
uv run --python 3.13 --with matplotlib==3.9.4 python docs/readme_charts.py
```

[README](../README.md) · [Upstream benchmark comparison](JEV-COMPARISON.md)
