# Historical measurements

> These campaigns predate the current native-read design. See [public-project benchmarks](PUBLIC-PROJECTS.md) and [current architecture](ARCHITECTURE.md) for the latest version. Historical names identify the versions actually measured.

Real Jev measurements use `jev-1.13.0` on three personal Flutter projects. Professional-project session analysis appears only as anonymous aggregates. Jev 1.13 pricing, confirmed September 29, 2026, is $0.042 per million input tokens with free output. [TypeSafe](https://docs.typesafe.ai/models). Confirming pricing does not resolve uncertainty about quality or overall savings.

The later corrected-v0.2 exploratory campaign cost $1.31 across four sessions: Gambade $0.1958 without / $0.2331 with; Pioudex $0.5644 / $0.3120. No `lens` calls occurred. It is reported [separately](EXPERIMENT-5USD.md), because conditions differ.

| Evidence level | Question | What it establishes |
|---|---|---|
| Integration | Does the plugin start, respect exclusions and handle outages? | Working mechanisms, not Jev relevance or savings. |
| Components | Does Jev find relevant passages, violations or memory entries? | Potential usefulness when the agent uses them. |
| Complete tasks | Does the agent use it, finish correctly and cost less? | The level needed to validate the overall promise. |

## Context use in existing sessions

49 sessions, 15,835 exchanges, four Flutter projects including one anonymized professional project. Usage is deduplicated by message. Costs use each model's API prices as of September 28, 2026; they are estimates, not invoices.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/context-growth-dark.svg">
  <img alt="Context tokens supplied on each exchange across real sessions." src="img/context-growth-light.svg">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/tool-residency-dark.svg">
  <img alt="Share of repeated context occupied by tool results, grouped by tool." src="img/tool-residency-light.svg">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/cost-by-context-dark.svg">
  <img alt="Share of exchanges and estimated cost by context size." src="img/cost-by-context-light.svg">
</picture>

- Mean context supplied per exchange: 250,000 tokens.
- Tool outputs account for 31.9% of repeated context. A tool output is supplied again a median of 17 times.
- Exchanges above 400,000 tokens account for 20% of exchanges and 47% of estimated cost.

Potential `lens` targets were full reads of files at least 150 lines long and outputs at least 80 lines long:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/lens-target-dark.svg">
  <img alt="Potential target share of repeated context: 13.9% on the professional project and 10.3% on personal projects." src="img/lens-target-light.svg">
</picture>

These are opportunity estimates, not savings. They assume roughly 2.3 characters per token and retention until the next compaction. Caching and subsequent necessary reads affect actual cost.

## Component measurements

September 28 measurements, before version 0.2. Search has since changed: the historical 20/20 result does not validate today's engine. Offline recalculation on September 29 reproduces the original 66/72 complete Jev selections and 53/72 local selections.

| Component | Result | Scope and limitations |
|---|---|---|
| `lens` | All expected passages in 66/72 cases (91.7%), versus 73.6% with BM25. Median 10.1% of file lines, or 12.9% of full-read characters including labels and omission notices. No passage shown for eight trap questions. About 0.45 s. | 36 questions on 12 files in French and English; translations are not independent cases. Source coverage is not answer correctness or task savings. |
| `lens find` | Correct file first for 20/20 descriptions; 95% interval 83–100%. 19/20 when retaining only confident results. Keyword ranking: 35%, or 5% with no shared code words; naive grep: 18%. About 1.6 s. | Questions written while reading source. Three successes on six vague descriptions; two false positives on eight close traps. Naive grep is not a complete agent search strategy. |
| Guard | 26/30 violations found, four missed; no warnings on 30 compliant cases. Identical results across three passes. About 0.3 s Jev time, in the background. | Mostly synthetic rules and examples written by the same agent. One rule per example, unlike real changes. |
| Memory | 20 entries suggested for 40 requests, 15 useful, against 58 needed. At least one useful entry for 14/34 requests needing memory. Top-three recall 60%, versus 47% with keywords. Skills: 4/6 correct, no false suggestion. About 0.4 s per request. | Catalog and descriptions matter as well as thresholds. |

**Label corrections:** reviewers found incorrect expected passages in the `lens` set. Corrected labels yield 98.6% for Jev and 79.2% for keywords. The table preserves the original labels' results.

## Initial complete-task pilot

September 29: Sonnet 5, one run per task and variant, real Jev, stopped early to preserve quota. Three tasks have paired results. Automatic criteria report 2/3 successes in both variants, with change review still missing. API-equivalent cost: $3.11 with the plugin versus $3.45 without. No `lens`, `dart-outline` or skill use; the guard ran without false warnings. This small incomplete pilot is not proof.

## Adoption campaign

`adoption-2026-09-29`: four Pioudex tasks at `91036cc`, Sonnet 5, one run per variant. Both plugin variants include guard and memory:

- `control`: no plugin.
- `all`: startup instruction and at most three hints per session for full Dart reads of at least 300 lines.
- `all_refuse`: startup instruction and one refusal of a large full read. This became the default at that time; current defaults differ.

Success required automatic checks and a reviewer not told the variant.

| Task | Control | Hint | Refusal |
|---|---|---|---|
| `loc-silence` | Failed, $0.96 | Passed, $0.80 | Passed, $0.67 |
| `diag-gain-xp` | Passed, $0.77 | Passed, $1.06 | Passed, $1.17 |
| `convention-olive` | Failed, $1.14 | Failed, $0.33 | Failed, $0.62 |
| `memoire-vibrations` | Failed, $3.35 | Failed, $3.97 | Failed, $2.67; stopped at 25 min |
| **Claude total** | **1/4, $6.23** | **2/4, $6.16** | **2/4, $5.12** |
| Jev input tokens | 0 | 32,197; about $0.001 | 125,808; about $0.005 |

### Code actually received

`bench/adoption.py` counts Dart text delivered through tools, including Read line numbers.

| Measure | Control | Hint | Refusal |
|---|---:|---:|---:|
| Full Read | 26 calls; 450,010 chars | 19; 318,533 | 8; 56,395 |
| Ranged Read | 12; 26,511 | 6; 25,247 | 9; 24,984 |
| `lens` | — | — | 10 calls; 1,367/5,995 lines; 72,564 chars |
| Shell, including `sed -n` | — | — | 2 calls; 3,235 chars |
| **Total Dart characters** | **476,521** | **343,780** | **157,178** |
| Full Dart files of at least 300 lines | 14 | 10 | 1 through `lens` |
| Displayed hints/refusals | — | 9 hints | 8 refusals |
| Full read requested again after refusal | — | — | 0 |

The complete file returned by `lens` had 507 lines. Claude asked about the whole settings-screen structure, and Jev selected all 23 chunks.

After refusals, the olive task made two `lens` calls and edited without rereading the region through Read. Diagnosis used `lens`, more searches and focused reads before fixing. Localization used `lens` and searches before answering. Vibrations continued with a long search/memory exploration before writing.

### Cost interpretation

The refusal total is 18% lower, including failures. Task-level ratios against control range from 0.54 to 1.52, median 0.74. On the two tasks accepted with both plugin variants, cost is nearly equal: $1.86 with hints and $1.83 with refusals. About 97% of the total difference comes from failed tasks.

Diagnosis, the only task accepted in all three variants, costs $0.77 without the plugin and $1.17 with refusal: about **52% more**, excluding Jev. One case establishes neither general gain nor general regression. The defensible finding is **67% less Dart code received**, without demonstrated savings on equally complete work. Active guard and memory also prevent isolating the refusal mechanism.

### Read-cost attribution, not a savings ceiling

`bench/ceiling.py` keeps its historical name but does not calculate the plugin's maximum possible saving. It attributes cost to large full Dart reads while assuming the rest of the workflow stays unchanged. It does not simulate searches avoided by `find`/`which`, the detour through `lens`, or Jev cost.

The calculation distinguishes model prices and five-minute/one-hour cache classes. Each Read belongs to its own agent context until compaction or agent completion. Repeated usage is deduplicated; persisted logs supplement terminal traces, including missing output usage.

Uncertainties include characters per token (2.3 or 3.5) and the billing class of each excerpt. Logs give per-call totals, not per-excerpt classes. The script reports extreme allocations compatible with those totals under text-retention assumptions; these are not confidence intervals.

Across seven controls, recorded calls cost $9.68. Selected reads account for $0.57–$2.23 under these assumptions. **That range is neither observed savings nor a product promise.** Earlier “at most a few percent” and “hundreds of trials needed” claims were withdrawn because this calculation did not support them.

```bash
python3 -B bench/ceiling.py '~/.cache/dartlens-bench/results/*/*.control.*' --json /tmp/jev-read-estimate.json
```

### Search-phase analysis

`bench/search_cost.py` retains analysis from `claude/savings-scope`. Calls before the first edit—or final answer for read-only work—account for 58% of seven controls' cost, or 48% excluding the first main-agent call. That phase also includes reasoning, tests and instructions: **it is not a share that search can necessarily save**.

Files later neither edited nor cited may still have ruled out a hypothesis. Tool-content attribution assumes retention within each context. No command or log establishes `find` or `which` use in the twelve plugin trials; command and log counts remain separate to avoid duplicate attribution.

```bash
python3 -B bench/search_cost.py --json /tmp/jev-search-analysis.json
```

## MCP visibility and answer completeness

The first MCP `find_code` used the same `lens find` engine. Local checks covered manifests, transport, the three expected Pioudex files, fake Jev, local fallback, scope rejection and cancellation/disconnection. The benchmark distinguishes MCP calls from commands/logs and does not count ranking text as Dart source. Recalculation on 19 archived trials remains unchanged.

### First real observation

Under a separately authorized $1 budget, one `pioudex-loc-silence` session used Sonnet 5 and the original French prompt. `find_code` was one of 106 available tools, including 75 MCP tools. It was deferred in both the main and Explore agents; neither called `ToolSearch`, `find_code` nor `lens`. Explore used ordinary search, with three large-read refusals and eleven partial Dart reads, eight in the subagent.

The reviewer accepted all four existing criteria, with an inaccurate comment attribution noted outside the rubric. No edits. Claude cost $0.598 and benchmark time was 157 s. Without a paired control, and without `find_code` use, this proves neither savings nor tool benefit.

The documented [`alwaysLoad: true`](https://code.claude.com/docs/en/mcp#exempt-a-server-from-deferral) setting was then added to the single-tool server. It exposes the description without prior search but does not force selection or override subagent tool restrictions.

| Session | `find_code` | Claude cost, excluding Jev | Review |
|---|---|---:|---|
| Adoption control | Absent | $0.96 | Rejected |
| Adoption hint | Absent | $0.80 | Accepted |
| Adoption refusal | Absent | $0.67 | Accepted |
| obs1, deferred tool | Unused | $0.60 | Accepted |
| obs2, `alwaysLoad` | Used | $0.29 | Rejected |
| obs3, repetition 1 | Used | $0.22 | Rejected |
| obs3, repetition 2 | Unused | $0.54 | Rejected |

The two tool-using sessions received model/UI-focused results without identification services. They omitted required `ConfidenceTier.parse` and failed to explain direct embedded construction without `Identification.fromJson`. **Both had nevertheless received `ConfidenceTier.parse` through a full Read.** Retrieval gaps and omission of already-read facts are separate problems.

Versions, exploration and review instructions differ. The last two reviewers were explicitly directed toward embedded processing. The missing `parse` criterion was pre-existing. These low costs are not successful product results.

### Engine revision and later observations

Review of [upstream `find.go` at e81c1d0](https://github.com/BorisLeMeec/jev/blob/e81c1d006b8b23a616486610f311039088521d0c/internal/run/find.go) found individual judgments and documented ranking degradation from large batches. The old local engine grouped 120 files into two requests, keyword-selected candidate chunks, then ranked all verified files ahead of others regardless of score.

The revision used per-file screening, the same relevance question for screening and full-source verification, score ordering and localization of at most three leaders. Oversized candidates remain explicitly unverified rather than presenting a prefix as a complete file. Hidden above-threshold candidates and incomplete flow coverage are reported. The default result count stays five; the change does not assume query translation fixes quality.

Offline checks replayed two French prompts over 120 pinned files: 120 screening calls, eight complete verifications and three localizations each, with controlled errors, oversized contents, rankings, uncertain locations and display limits. Fake Jev validates integration only. Later version 0.3.2 uses smaller, separately judged groups; see [current benchmarks](PUBLIC-PROJECTS.md).

Two later real searches place `embedded_bird_identifier.dart` fifth. `repli_bird_identifier.dart` remains outside the eight verified candidates. Archive `jev-search-2026-09-29`: 262 calls, 285,260 input tokens and 6,144 output tokens.

| Session | `find_code` | Claude cost, excluding Jev | Benchmark time | Result |
|---|---|---:|---:|---|
| obs4 | Used | $0.2712 | 52.7 s | Rubric accepted; factual error outside rubric |
| obs5, repetition 1 | Used twice | $0.2474 | 65.7 s | Rejected |
| obs5, repetition 2 | Unused | $0.3355 | 103.7 s | No answer; budget exhausted |

obs4 names required symbols but places a common conversion before the listening/photo split. Listening actually tries the embedded engine first and constructs `Identification` directly; photo uses the server. The engine file was suggested but unopened. obs5 r1 repeats this shortcut and omits `ConfidenceTier.parse`. Historical judgments remain visible, but their different strictness prevents a quality-equivalence conclusion.

obs5 r2 ends at `error_max_budget_usd` after a waiting message. A subagent report was initially mistaken for its final answer; benchmark fallback now excludes subagent text. The attempt remains a failure. The $0.30 Claude cap did not prevent $0.3355 usage. Session subagents count toward that cap; Jev and separately launched reviewers do not. [CLI reference](https://code.claude.com/docs/en/cli-reference).

These observations do not prove a quality-preserving benefit. The remaining problem is stopping before all required branches are checked, which a longer result list or another instruction alone does not resolve.

## Regression and timing corrections

Replaying all twelve adoption results on clean copies reproduces the checks. Initial state passes 339 tests, analysis and formatting, except for the deliberately seeded diagnosis bug.

- All three vibrations variants break two previously passing tests. Control/hint move the About card outside the test screen; refusal leaves an unused translation key and stale generated file. The reviewer did not see tests, so its “no regression” judgment did not cover them.
- Olive fails in all variants. Automatic criteria already passed without edits. No variant checked all color effects: cream text has 4.55:1 contrast, while the watermark falls near 1.34:1, below the design-system minimum. The rubric predates the campaign; causality cannot be assigned to the plugin.
- Vibrations never completes: control stops at 60 turns, hint leaves a hanging background test, refusal stops at 25 minutes. A 299 KB `DECISIONS.md` costs seven to nine detour turns. The router correctly ranked five useful entries first, without completing the task.
- Four tasks with one run each are insufficient for `score.py` to issue a quality verdict.

Twenty-six permission requests waited roughly 115 seconds before denial. The user `rtk` hook rewrote allowed commands outside the allowlist. A cmux launcher preceded the real Claude executable; involvement was suspected but not directly established. Vibrations lost 691 s without the plugin, 461 s with hints and 807 s with refusals. **Adoption-campaign durations are unusable for speed claims.** Individual `lens` calls took under a second, but this does not establish overall impact. The runner now skips user settings and terminal wrappers by default; see [protocol](../bench/PROTOCOL.md).

## Reproduction and next steps

The [later four-session campaign](EXPERIMENT-5USD.md) followed a [frozen validation plan](VALIDATION.md). Overall benefit remained inconclusive. Future experiments need unfamiliar tasks, justified whole-file reading and repeated trials; this historical plan authorizes no new spending. Future olive criteria should make reporting checks explicit; vibrations needs a revised turn budget. Do not retroactively rescore only one variant.

Context-use figures come from `docs/need_data.py`, `docs/charts.py` and `docs/lens_opportunity.py`. Task execution and scoring are in [bench/PROTOCOL.md](../bench/PROTOCOL.md).

Historical adoption charts use [twelve exported rows](readme-results.json), with token classes, prices and source hashes. They show all-attempt code volume and, separately, the sole diagnosis accepted in all variants. Public aggregates reproduce charts, not every private answer review.

```bash
python3 -B bench/adoption.py ~/.cache/dartlens-bench/results/adoption-2026-09-29 --json /tmp/jev-adoption.json
python3 -B bench/score.py ~/.cache/dartlens-bench/results/adoption-2026-09-29 --reviews ~/.cache/dartlens-bench/reviews/adoption-2026-09-29/reviews.json --key ~/.cache/dartlens-bench/keys/adoption-2026-09-29.json --json /tmp/jev-scores.json
python3 docs/readme_charts.py --adoption /tmp/jev-adoption.json --scores /tmp/jev-scores.json
```

To regenerate delivered chart data only:

```bash
uv run --with matplotlib==3.9.4 python docs/readme_charts.py
```

Light and dark charts use identical data. Offline redrawing does not validate a newer plugin version.
