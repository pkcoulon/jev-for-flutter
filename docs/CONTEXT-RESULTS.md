# Parallel context trials — September 29, 2026

> Historical results. Version 0.3 uses native focused reads and keeps automatic context optional. See the [current measurements](PUBLIC-PROJECTS.md) and [architecture](ARCHITECTURE.md).

Two plugin versions are measured separately. The first four sessions exposed a context-delivery problem; the format was then fixed. All runs remain included.

## Initial version: two information searches

One session per task and variant, Sonnet 5, medium effort, identical prompts and criteria within each pair. Pinned personal projects, no customer repositories. Astra reviewed in the main session, **neither independently nor blind**.

| Measure | Pioudex without / with | Gambade without / with |
|---|---:|---:|
| Claude tokens, including cache | 440,317 / 358,347 | 436,731 / 449,198 |
| Claude + Jev cost | $0.3796 / $0.2964 | $0.2109 / $0.2194 |
| Runtime | 119.1 / 74.6 s | 32.4 / 42.3 s |
| Token change | −19% | +3% |
| Cost change | −22% | +4% |
| Time change | −37% | +31% |

**No answer covers every criterion fixed before this campaign.** On Pioudex, the plugin omits the embedded engine; the control mentions it but omits `ConfidenceTier.parse` and construction without JSON. On Gambade, both give the correct threshold and source but omit the assistant weather-tool connection. No files were modified. The favorable Pioudex differences therefore do not establish savings on complete work.

Automatic preparation ran in both plugin sessions: Jev finished in 2.7 seconds on Pioudex and 5.4 seconds on Gambade, with delivery to the subagent and parent respectively. Eight successful ranking requests per prompt. Claude did not need to discover the MCP tool.

### Delivery problem and fix

Claude Code placed the 11.4 KB result in a file, exposing only its first 2 KB in the subagent conversation. The plugin now caps automatic delivery at **8,000 bytes, including UTF-8 encoding**, reserves room for coverage limits, and groups possible implementations of the same method.

All 41 local checks pass. Offline replay of the eight Pioudex judgments on the same blocks produces compact context containing conversions, listening/photo flows, embedded processing and fallback, without new Jev calls. This format check does not establish that the LLM will cover them all.

## Compact format: one fix with tests

After the delivery problem, one final pair evaluated the corrected format on Pioudex's XP calculation task. This differs from the two incomplete information tasks, which were not rerun. The plan was frozen before calls: control then plugin, each capped at $0.85 Claude, with Jev and reserve inside the remaining $5 budget.

| Measure | Without plugin | Compact context | Change |
|---|---:|---:|---:|
| Claude tokens, including cache | 574,721 | 761,844 | +33% |
| Claude + Jev cost | $0.2818 | $0.3446 | +22% |
| Claude session | 141.0 s | 112.8 s | −20% |
| External checks | 26.1 s | 22.7 s | — |
| Total through completed checks | 167.1 s | 135.5 s | −19% |

Both variants make exactly the same one-line fix: restore the rank-4 multiplier from ×4 to ×5. Tests are unchanged. Traces confirm **1,067 passing tests in each session**; all five external checks also pass: celebration, progression, regression, analysis and formatting. Both answers are accepted for this task.

The hook delivers **7,677 bytes directly into the conversation**, without externalizing them. The transport fix is therefore checked in a real session. That does not turn the earlier incomplete localization answers into successes.

Claude makes 16 calls with the plugin versus 13 without it. The added cost is mostly Claude; Jev costs $0.000831 across this pair, including connectivity checks. The lower time is one observation; order, caching and latency may contribute. It is not a general “19% faster” claim.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/context-results-dark.svg">
  <img alt="Same fix: 33% more tokens, 22% higher cost and 19% less time in one pair of sessions." src="img/context-results-light.svg">
</picture>

**Product decision:** automatic context and parallel execution work, but the full objective—preserved quality, fewer tokens, lower cost and faster completion—is not established. Extra context can trigger extra exploration, so more context is not enabled by default. Automatic context is now optional.

## Cost and evidence

The first four sessions cost **$1.1064**, then the compact-format pair **$0.6264**, at API-equivalent prices including Jev and connectivity checks. Adding the earlier **$1.3053** yields **$3.0381, or $3.04 of $5** at this stage. No cap overrun, retry of incomplete answers or extra paid reviewer. Conservative accounting keeps the larger of native and recalculated costs; the difference is below $0.0001.

Logs distinguish Claude fresh input, five-minute cache writes, one-hour cache writes, cache reads and output. Jev usage is separate. Durations include tools used by Claude; the information-search tasks required no external test commands. Copy preparation and review are excluded.

Private archives: `~/.cache/dartlens-bench/context-real-2026-09-29/` and `context-final-2026-09-29/`, containing plans, snapshots, Jev requests and responses, Claude/subagent traces, diffs, usage and reviews. Keys are not archived. The initial and compact versions have distinct fingerprints.

Exported data: [initial version](context-initial-results.json), [compact format](context-final-results.json). They include cache classes, durations, prices, review reservations and evidence fingerprints. Regenerate charts with `uv run --with matplotlib==3.9.4 python docs/readme_charts.py`.

[Architecture](ARCHITECTURE.md) · [Local checks](CONTEXT-REDESIGN.md) · [Earlier measurements](EXPERIMENT-5USD.md)
