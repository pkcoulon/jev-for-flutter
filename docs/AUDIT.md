# Initial audit — September 29, 2026

> Historical audit of version 0.2. Version 0.3 uses native focused reads and keeps automatic context optional. See the [current measurements](PUBLIC-PROJECTS.md) and [architecture](ARCHITECTURE.md).

A [parallel-context redesign](CONTEXT-REDESIGN.md) and [six real sessions](CONTEXT-RESULTS.md) followed this audit within the cumulative $5 budget. They changed triggering, the MCP engine and defaults. The checks below evaluate the earlier version, not that new architecture.

**Verdict at this stage: selection reduces code received in archived trials, but token savings, faster completion and preserved quality on completed work are unproven.** The mechanisms are testable; the full product claim would be premature.

The audit started at `0de8979`, declared version `0.2.0`, followed by the local fixes below. Initial work was offline, with no real calls or builds. After $5 authorization, [four real sessions](EXPERIMENT-5USD.md) completed the audit for $1.31, without new builds. Those fixes were unpublished at the time; they are now incorporated into later releases.

## Scope

Manifests, hooks, commands, skill, MCP server, transmission policy, Jev client, Dart parser, chunking, search, conventions, memory and usage accounting. Synthetic-file checks with a local fake HTTP server, plus separate recalculation of previously paid real trials. The [architecture](ARCHITECTURE.md) describes current entry points, data flows, deadlines and fallbacks.

Checks used macOS, Python 3.9.6 and Claude Code 2.1.284 for manifest validation. Dart positions were checked with an already-cached compiled helper, without building. Linux and installation by an unrelated GitHub account were not tested in this initial audit.

## Reproduced defects and fixes

| Defect | Effect | Fix and check |
|---|---|---|
| Executables absent from Claude's `PATH` | Fresh installations recommend an unavailable `lens` command | Startup hook writes `PATH` to `CLAUDE_ENV_FILE`; commands and help work from `/usr/bin:/bin`; suggestions quote paths containing spaces. |
| Cap checked without a shared lock | Concurrent reads can all pass before markers exist | Per-session lock protects counting and marker creation. Controlled case changes from eight refusals under a cap of three to three of twelve concurrent requests; one refusal per file remains. |
| Excluded nested repository accepted by `sendable` | Its source could be sent from an authorized parent | Check enclosing Git remotes for every path. Synthetic excluded repository, external symlink and invalid policy are refused. No customer source used. |
| PEM masking covered only headers | Key bodies or later blocks could remain in content or labels | Mask full blocks before chunking, preserve positions and neutralize labels. Checked on three blocks and long lines; known-format filtering is not universal secret detection. |
| Invalid Jev answers allowed `find` to continue | Unnecessary calls and misleading judged-file counts | Require a valid score before continuing and count only usable judgments. Eight invalid answers trigger fallback without further candidates. |
| Missing Jev output-token logs | Incomplete usage accounting | Record input and output returned by the API. Historical missing values stay unknown rather than becoming zero. |
| `dart-outline` ignored `DARTLENS_OUTLINE_NO_BUILD` | Helper compilation could occur despite the restriction | Propagate the flag through both helper paths and explicitly reject `--build`. Included before the four real sessions. |

## Checks performed

**56 local checks passed**, using two temporary scripts retained with audit evidence:

- Fresh `PATH`, activation, disablement, suggestion modes, repeated, partial and concurrent reads.
- Exclusions, symlinks, unreadable policies, multiline secrets and preserved positions.
- Excerpt selection through the fake HTTP contract, command output, exit codes and raw-file permissions.
- Search across 170 files: at most 150 initial judgments, with later verification accounted separately.
- HTTP 401: eight attempts; HTTP 529: 24 including retries; invalid scores: eight then fallback.
- MCP initialization, no default tools, activation, invalid arguments, external paths, local search, shutdown and process-group cancellation.
- Controlled convention and router inputs.

Marketplace and plugin manifests pass strict validation; all twelve benchmark definitions pass `bench/run.py --check-tasks`. This does not mean all twelve tasks were rerun or their criteria are sufficient. Fake responses validate integration and fallback, not semantic relevance.

## What the real data supports

The subsequent corrected-version campaign covers two tasks, one session per variant. Combined cost: Gambade $0.1958 → $0.2331; Pioudex $0.5644 → $0.3120. Pioudex fixes match and pass tests. Gambade answers are accepted with precision reservations. Review is not independent. No `lens` use or large-read refusal occurred, so this campaign demonstrates no selection benefit. [Tokens, durations and evidence](EXPERIMENT-5USD.md).

Earlier adoption recalculation gives **476,521 → 157,178 Dart characters**, **67.0% less**, including failures. It predates 0.2 and does not count the whole conversation.

The only task accepted in all three variants provides a counterexample to an overbroad savings claim:

| Claude measure, diagnosis task | Without plugin | With read refusal |
|---|---:|---:|
| Fresh input | 44 | 46 |
| One-hour cache writes | 89,206 | 131,492 |
| Cache reads | 1,791,949 | 2,813,838 |
| Output | 5,389 | 7,765 |
| Recorded API-equivalent cost, excluding Jev | $0.7692 | $1.1665 |

Here, less code received accompanies greater task cost. One repetition cannot establish a general increase, but it shows why code reduction is not proof of overall savings. Five-minute cache writes are zero; main and subagent contexts are accounted separately.

Original `lens` measurements recalculate to **66/72 complete selections with Jev**, versus **53/72** locally. Median lines shown are 10.1%, but six selections are incomplete. French and English versions of one question are not independent cases.

Early `find_code` sessions also produced incomplete low-cost answers. Sometimes an already-read fact was omitted; sometimes a suggested file was never opened. Query language and result count alone do not explain these failures. [Data](readme-results.json) · [Historical measurements](MEASURES.md).

## Initial technical decision

Keep `find_code` off by default. File ranking does not establish coverage across services, models and UI. More sessions without addressing that limitation can repeat the same omissions.

Conventions and memory are supplementary helpers with evidence on limited sets. They also add calls or context and belong in the installed product's cost.

At this stage, one-time refusal remained the default with a full-read escape. Later releases replaced it with native focused reads. Earlier adoption showed triggering, not universal `lens` use; the corrected-version campaign showed that partial reads can bypass the trigger entirely. [Protocol](VALIDATION.md) · [Report](EXPERIMENT-5USD.md).

## Publication follow-up

The repository is now public, MIT text is present at the root and inside the package, and marketplace installation has been checked. Those items were unresolved during the initial audit. See [first-time setup](FIRST-RUN.md).

Remaining limits are explicit: no universal ten-second deadline or exhaustive feature coverage; optional CLI helper preparation; incomplete secret-pattern coverage; and no general benefit inferred from loading hooks successfully. Current search caps and read behavior are described in the [architecture](ARCHITECTURE.md).
