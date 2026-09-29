# Benchmark protocol

This runner asks whether Claude Code with Jev completes real Flutter tasks more reliably, or equally well at lower cost. For the current public-project campaign, see [its dedicated protocol and results](../docs/PUBLIC-PROJECTS.md). This document covers the original complete-task runner and its historical variants.

**Never infer Jev relevance or savings from the fake server.** It validates transport, failure handling and logging. Its lexical responses are not the real model. `score.py` suppresses verdicts for trials that use it.

## Questions and hypotheses

| Component | Question | Hypothesis to challenge | Evidence against it |
|---|---|---|---|
| `lens`, `find`, `which` | Does the agent find information sooner without missing it? | Equal success, lower cost or time per successful task | Lower success or systematic full-read fallback |
| Convention guard | Does quick post-edit feedback improve compliance? | More convention-task successes without burdening other work | Ignored or false warnings; cost without benefit |
| Memory and skills | Does routing surface useful entries at the right time? | More memory-task successes without missing useful entries | Relevant entries omitted or unnecessary context injected |

The memory control receives native Claude memory: `MEMORY.md` plus readable entries. `all_nojev` separates local plugin behavior from Jev's contribution.

## Variants and isolation

The runner retains legacy environment names, recognized by the current compatibility layer.

| Variant | Plugin | Disabled components / setting |
|---|---|---|
| `control` | No | No plugin configuration |
| `lens` | Yes | `DARTLENS_GUARD_DISABLE=1`, `DARTLENS_ROUTER_DISABLE=1` |
| `guard` | Yes | `DARTLENS_LENS_DISABLE=1`, `DARTLENS_CONTEXT_DISABLE=1`, `DARTLENS_ROUTER_DISABLE=1` |
| `router` | Yes | `DARTLENS_LENS_DISABLE=1`, `DARTLENS_CONTEXT_DISABLE=1`, `DARTLENS_GUARD_DISABLE=1` |
| `all` | Yes | None |
| `all_nojev` | Yes | `DARTLENS_JEV_DISABLE=1` |
| `all_refuse` | Yes | `DARTLENS_LENS_NUDGE=refuse_once` |

Every trial receives `DARTLENS_BENCH_RUN=<campaign>/<trial>/<session>` and a fresh `DARTLENS_STATE_DIR` for usage, guard and router logs, circuit breakers, queues and catalog cache. This prevents one trial's outage state or logs from contaminating another. Legacy `lens` logs outside that directory are attributed by bounded run tag, session ID or, as a last resort, time window (`window_attributed`).

Disabled components must inject nothing and make no Jev calls. The runner checks component switches; `--allow-unisolated` explicitly bypasses that check. Descriptions of disabled tools may remain in context, so their fixed token cost is still observable.

For every remote-enabled variant, the exact trial environment must satisfy `policy.jev_allowed`: key, policy and project activation. Failure stops the campaign. The first such trial also sends a constant connectivity question without project data; `--no-jev-ping` skips this for transport checks. `score.py` suppresses verdicts when there are no successful Jev calls or errors exceed 10%, configurable through `--max-jev-errors`. Missing-key and open-circuit events are logged too.

Controls must not load a separately installed copy of the plugin. The runner checks enabled-plugin settings. Project plugin configuration is written only in plugin variants and excluded locally from Git.

## Common conditions

- Same model, permission mode and `--allowedTools` in every variant. `lens` and `dart-outline` may be allowed for both but exist only with the plugin. Additional MCP/LSP tools passed through `--extra-arg` must be identical.
- Same effective command permissions: `lens "Q" -- COMMAND` executes outside Claude's ordinary command approval. The runner installs a `PreToolUse` gate through `--settings` to apply the same allowlist, including shell wrappers, pipelines and redirections. `--settings` is reserved for that gate. In `bypassPermissions` mode, all variants have no gate or allowlist.
- Independent disposable repositories in random system-temporary paths. With `keep` history, only the pinned commit and ancestors are fetched. With `orphan`, `git archive` is committed alone. Branch name is `main`, without variant identifiers. Source remotes remain for policy enforcement. `task.json` is exported only after Claude exits; setup patches are not saved where the agent can read them. Dependency preparation precedes the trial and belongs to its base commit.
- Source repositories pass policy checks before copying, including validation and `--dry-run`. Excluded projects stop the operation.
- Variant order rotates by task/repetition block, and task order changes by fixed seed. Prompt-cache effects remain possible; `--pause 360` can exceed the five-minute cache TTL, otherwise rotation distributes order effects.
- `--lang alternate` uses one language per block, identical across variants. `--lang both` doubles blocks. The original pilot design calls for at least three repetitions per task and variant.
- User settings are excluded by default with `--setting-sources project,local`. `--user-settings` restores them for every variant. This avoids personal hooks such as command rewriting through `rtk`.
- The real Claude executable is used rather than terminal wrappers such as cmux. `--claude PATH` overrides discovery. Earlier permission waits lasted roughly 115 seconds each; wrapper involvement was suspected, not established.
- Every trial is one attempt. Task failures, deadlines and denied permissions count with their cost. Infrastructure failures—quota, overload, rate limits, authentication or no CLI response—are classified `infra_failed`, archived in `infra-N/`, and retried on resume. Their costs are reported separately rather than hidden. Quota/authentication failure stops the campaign.
- `campaign.json` freezes model, permissions, tool list, CLI arguments, deadlines, Jev backend/URL, plugin fingerprint and Claude version. Changed conditions reject resume unless `--force` explicitly overrides it. Runtime changes stop a campaign; heterogeneous campaigns receive no verdict.

## Tasks

Each `tasks/<id>.json` defines a project and pinned commit, task type, `prompt_fr`, `prompt_en`, setup patch, `keep`/`orphan` history, seeded memory, `expect_before`, reference diff/answer, executable criteria, review rubric and expected files. `_projects.json` maps source paths and preparation. Guard rules use schema v1: English yes/no questions where yes means a violation, plus `true`, `false`, `message`, `applies_to` and examples.

- `--check-tasks` validates task definitions and project rule schemas.
- `--validate-setup` prepares tasks without Claude, checks `expect_before` and sends representative edits through each guard, requiring a logged verdict. Fake Jev is suitable only for transport validation.
- `--validate-reference` applies setup and the reference diff, then requires executable and answer criteria to pass. Missing references remain explicitly unverified.
- Hidden criterion files exist only while that criterion runs; analyze and format judge the agent's final tree.

The original set contains twelve definitions: five Pioudex localization/diagnosis/i18n/convention tasks, one Pioudex synthetic-memory task, five Gambade tasks covering heat, daylight-saving symptoms, bilingual labels, an eleven-file UTC fix and a UTC convention, and one Panorameuh real-memory task. The Panorameuh task remains excluded while `todo`. A valid definition is not a validated reference or evidence of task quality.

The initial verified reference was `gambade-convention-jours-sans-balade`; other references must be checked before a larger pilot. Coverage includes useful generated localization code, ambiguous names, parameterized labels, implicit conventions, multiple memory entries, differing project conventions, and French/English prompts. Preserve recorded prompts and answers in their original language.

## Measures

**Primary criterion: correct completion without regression.**

1. Require all executable checks: tests, analysis, formatting, hidden tests, grep, diff constraints and localization answers.
2. Export variant-masked review packets with `score.py --export-review DIR --key KEY`. Stable HMAC IDs hide trial names. Packets include the request, rubric, answer, Git commands, flags and diff. Tool-identifying sentences are removed in every packet, with a constant notice. The operator sees redaction rates by variant and an imbalance warning. Store the key outside the reviewer directory. Re-export adds new trials without overwriting existing reviews. Reviewers must fill both `accepted` and `regression`.

A success passes executable criteria, is accepted, and has no regression. Missing review fields make the result provisional; no verdict is issued.

Secondary measures:

- Time to a successful result, including required verification.
- API-equivalent cost per successful task: deduplicated message usage and tool results, five Claude token classes, dated model pricing and a separate uniformly weighted comparison. Divide all-attempt cost, including failures, by successes. This is not an invoice or subscription-quota estimate.
- API calls, tool results, `lens` use and Git commands.
- Flags for access to original history, refs, reflog, benchmark files, other trials or Claude transcripts; include them in review packets.
- Jev requests, errors, unavailability, p50/p95 latency and hook-injected context, excluding the benchmark's own gate.
- Permission denials. `claude -p` cannot receive human intervention; tasks requiring it fail.

Report totals and distributions by task, never only an average of ratios. Show both the ratio of total costs and the distribution of task-level ratios. No verdict with fake Jev, heterogeneous conditions, incomplete review or unavailable Jev.

## Scaling an experiment

1. **Integration:** two or three tasks, one repetition, fake server and a test key. Check variant loading, log attribution and criteria. Interpret no performance numbers.
2. **Pilot:** expand to 20–30 tasks with verified references, three repetitions, real key and pinned Jev model. Estimate variance and identify unhelpful components. A pilot does not prove equivalent quality.
3. **Decision:** predeclare a non-inferiority margin, review the default ten percentage points, and size the next campaign from observed variance. Bootstrap by task: repetitions of a task are not independent tasks.

Set a spending budget before real calls. Sample size alone is not proof.

## Commands and artifacts

From the repository root:

```bash
python3 bench/run.py --check-tasks
python3 bench/run.py --validate-setup --jev-url http://127.0.0.1:PORT
python3 bench/run.py --validate-reference
python3 bench/run.py --dry-run --model MODEL --reps 3
python3 bench/run.py --model MODEL --reps 3 --campaign pilot-1
python3 bench/score.py ~/.cache/dartlens-bench/results/pilot-1 --export-review /tmp/review-pilot-1 --key ~/.cache/dartlens-bench/keys/pilot-1.json
python3 bench/score.py ~/.cache/dartlens-bench/results/pilot-1 --reviews /tmp/review-pilot-1/reviews.json --key ~/.cache/dartlens-bench/keys/pilot-1.json --json pilot-1.json
```

The real campaign command makes paid calls; the validation commands may invoke project preparation or tests. They are not installation steps.

Trial artifacts under `~/.cache/dartlens-bench/results/<campaign>/<trial>/` include `meta.json`, `transcript.jsonl`, persistent `session/` transcripts, `stderr.log`, `diff.patch`, `changes.json`, `checks.json`, `dartlens_logs.jsonl`, isolated `state/`, `task.json` and infrastructure-failure directories. Campaign conditions and resumes live in `campaign.json`; `_preflight/` holds connectivity logs. Keep these private when they contain project source, prompts or personal context.

## Known limitations

- Recheck `cc-usage` pricing before a new campaign; `score.py --prices` overrides it. Native `total_cost_usd` remains in detailed data, separately from recalculated totals.
- Mirrors/results live under the benchmark cache. Disposable repositories are deleted unless `--keep`; Claude's own session folders remain under its projects directory and are distinct from real-project paths.
- An agent can still read other trial archives or transcripts through ordinary absolute-path tools. These accesses are flagged, not technically prevented.
- The benchmark gate approximates Claude's command-prefix rules and rejects command substitution and file redirection. Some ordinarily approved read-only commands remain denied behind `lens --`, mildly disadvantaging plugin variants.
- Hook accounting depends on Claude's transcript format. Redaction can hide sentences but cannot guarantee that a reviewer cannot infer a variant from behavior.
- Pioudex memory entries are synthetic; Panorameuh was planned for real entries. Grep/diff criteria approximate conventions; review decides borderline cases.
