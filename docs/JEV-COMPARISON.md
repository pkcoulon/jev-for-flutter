# Upstream Jev: code and benchmark comparison

September 29, 2026 review of **all Go source files, tests, benchmark scripts and manifests** at [BorisLeMeec/jev, commit e81c1d0](https://github.com/BorisLeMeec/jev/tree/e81c1d006b8b23a616486610f311039088521d0c). Static inspection only; no build or new trial of that plugin. Promotional images are not evidence.

## Why its results differ

The upstream engine replaces some reading and search work. Our background-context experiment sometimes added a second exploration: on the latest fix, Claude made 16 calls versus 13 without the plugin. Useful savings require avoiding calls or content, rather than simply increasing Jev activity.

| Reported upstream measure | Comparison | Scope |
|---|---|---|
| −30% input tokens | Seven search pairs; a “Jev first” instruction versus search without Jev | Localization only, no edits or tests; one run per variant |
| −38% input tokens | Three audit pairs covering 12–18 files | One omission with Jev; unequal quality |
| −41% input tokens | Three pairs of full Hugo file reads versus focused ranges | Favorable read-reduction case, not completed development |
| 118× “leverage” | Volume examined outside the conversation / volume returned | Not measured Claude savings |

Sources: [search](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/tokenecon/TOKENS.md), [audit](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/tokenecon/TOKENS_ASK.md), [reads](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/hook/RESULTS_HOOK.md), [ratio calculation](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/usage/report.go).

These are useful signals, not universal 30–41% savings or equivalent dollar reductions. The script adds fresh input, cache writes and cache reads without weighting their prices. Claude output and Jev cost are outside the percentage. Tool-result token sizes are estimated as characters divided by four. [Counter implementation](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/agentstats.py).

Timing is mixed: the median with/without ratio for `find` is **1.03**, or +3%. A favorable mean is largely driven by one absent-feature case. The upstream README itself distinguishes token savings from general speed gains. [Timing report](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/TIMING.md).

## Architecture comparison at version 0.3

| Component | Upstream | Jev for Flutter 0.3 |
|---|---|---|
| Search | One judgment per file; eight concurrent requests; source verification of leaders; final localization | Same principle in `jev-flutter find`, without lexical prefiltering; exceeding the cap requires a narrower folder or `--max-files` |
| Large reads | Select a range from the entire file; update `Read.offset/limit` | Native focused reads, without refusal or voluntary lens call; additional scope question, masked source and per-project policy |
| Uncertainty | Original read on errors, low confidence or files above 80 KB | Original read on errors, broad requests, low confidence, files above 64 KB or changed source |
| Multiple files | Parallel requests, one per file | Parallel search retained; automatic context is optional |
| Conventions | Change classification, explicit opt-in and rules | Existing guard retained; no warning when no rule applies |
| Memory | No equivalent component in that repository | Existing router retained; not evidence of savings |

Version 0.3.2 additionally [batches file outlines](PUBLIC-PROJECTS.md), retaining a separate score per file.

Sources: [find.go](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/run/find.go), [hook.go](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/run/hook.go), [locate.go](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/run/locate.go), [lint.go](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/run/lint.go). MIT attribution is preserved in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Limits visible in the public code

- Transcripts, task/session mappings and private question sets are unpublished. Table totals can be recalculated, but final quality cannot be independently reviewed from the repository alone. Some Hugo/Prometheus localization cases are public; the read script does not pin their revisions.
- `find` answer scoring checks expected-path recall without penalizing extra paths on positive cases. It does not review the complete explanation. [report.py](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/tokenecon/report.py).
- The counter does not deduplicate repeated API response IDs. This creates a risk if transcript fragments repeat usage; without original traces, actual double counting cannot be established.
- `verifyTop` truncates at 90,000 bytes while still marking the file verified. Screening can lose files on errors while reporting the original count as scanned. Our automatic read does not split an oversized file into independent judgments.
- Cost estimation in `scan` assumes batches of 25 files while `find` sends one request per file. It underestimates requests and omits later passes. [scan.go](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/run/scan.go).
- The hook puts its note at the top level of the response JSON. The Claude Code contract expects `hookSpecificOutput.additionalContext` for `PreToolUse`; our adaptation uses it and checks actual delivery. [Official schema](https://code.claude.com/docs/en/hooks#pretooluse-decision-control).
- The installed hook references `bin/jev`, absent from tracked files, with no installation hook to build it. Fresh installation through marketplace commands alone therefore assumes an additional build/copy step. This distribution uses Python, with no required binary build.

These limits qualify the comparison; they do not invalidate delegated reading.

## Why TypeSafe spending stays small

The account screenshot used during the review showed **19,089,427 tokens, 2,538 requests and $0.7699** over seven days across all traffic. It indicates substantial Jev activity, but does not measure avoided Claude calls or isolate our latest campaign.

Jev 1.13 charges **$0.042 per million input tokens**, with free output. The relevant product measure remains **combined Claude + Jev cost for a correct answer**, including cache categories and observed time. [TypeSafe pricing](https://docs.typesafe.ai/models).
