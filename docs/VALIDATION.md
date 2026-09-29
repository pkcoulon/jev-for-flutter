# Validating benefits on completed work

> Historical protocol. Version 0.3 uses native focused reads and keeps automatic context optional. See the [current measurements](PUBLIC-PROJECTS.md) and [architecture](ARCHITECTURE.md).

The comparison below ran **before** the [parallel-context redesign](CONTEXT-REDESIGN.md). The following six sessions and their frozen versions are in [CONTEXT-RESULTS.md](CONTEXT-RESULTS.md). The final fix passes both variants' checks, but the plugin adds tokens and cost in that pair. A symbol appearing in a map does not validate the final answer; incomplete localization cases remain in the results.

**Status: the exploratory $5 campaign finished on September 29, 2026, spending $1.31 including Claude and Jev.** [Full report](EXPERIMENT-5USD.md). The frozen plan was followed: Gambade heat, without then with the plugin, $0.65 cap each; Pioudex XP diagnosis, with then without, $1.25 each. One repetition, no retries or paid external review. Results are mixed, with no `lens` use: savings at equal quality are unproven. Astra's main-session review is neither independent nor blind. No additional campaign was launched under this plan.

## Question and comparison

Does the locally fixed plugin, using defaults, complete a correct task with fewer tokens, less time and lower cost than Claude Code alone?

Keep the user prompt identical:

- **Control:** Claude without the plugin, hooks or MCP tools.
- **Plugin:** the same Claude with the then-current defaults: one-time refusal, configured guard and memory enabled, `find_code` disabled.

This evaluates the installed product. Isolating only `lens` would be a different experiment. Do not add a new variant after every disappointing result.

## Before the first call

Freeze plugin and personal-project commits, model and parameters, rules, memory, permissions and tool versions. Use the real Claude executable without user hooks that affected earlier trials. Do not preload expected answers into prompts or memory.

Prepare varied development tasks, including a flow crossing service, model and display, and a task where reading a complete file is justified. The twelve existing definitions are syntactically valid; that does not establish criterion quality. Validate initial state and reference answers before use.

For each task, predeclare the expected outcome, required branches, facts to explain or behavior to change, forbidden regressions and executable checks. A major omission or false explanation fails the task even if an older four-point rubric passes. Do not revise criteria for just one variant after seeing answers.

## Bounded execution

A small budget funds exploration, not general statistical proof. Fix task and repetition counts after checking recent baseline cost, reserving enough to finish the campaign and include Jev. A budget covering one pair yields one paired observation.

Alternate variants on disposable copies and fresh sessions. Retain failures, incomplete outputs and overruns. Do not stop solely when results become favorable or retry only plugin failures.

`--max-budget-usd` limits Claude sessions but the last call can exceed it; Jev and separately launched reviewers are outside it. Track cumulative spending externally, retain a reserve, and start no session unless the remaining balance covers its cap and reserve. Unconfirmed Jev pricing is unknown, not zero.

## Measures and decisions

| Priority | Measure | Rule |
|---|---|---|
| Quality | Complete correct result, tests, regressions and variant-masked review | A cheaper wrong answer fails; do not claim savings at equal quality without meeting that condition. |
| Usage | Claude fresh input, five-minute/one-hour cache writes, cache reads, output; Jev input and output | Count main and subagent usage once each. Preserve categories rather than a character total. |
| Cost | Claude and Jev valuation at dated prices | Publish all-attempt costs and successful counts, then paired comparisons accepted in both variants. Keep failed-attempt cost visible. |
| Time | Complete duration through result and verification | Include Jev, search and fallback. Annotate external waits without selectively excluding them. |
| Adoption | Spontaneous use and reading path | Explains the mechanism; does not validate quality or savings. |

Show dispersion and task-level results. An ambiguous small sample is **inconclusive**. An arbitrary sample count or 15% reduction threshold cannot guarantee proof. General preserved-quality claims need a predeclared non-inferiority margin and a sufficiently powered analysis; repetitions depend on observed variance.

## Product limitation

`lens` and `find` do not certify behavioral coverage. Earlier trials show that suggested files and even already-read functions can be omitted from final reasoning. Before enabling `find_code` by default, test complete flows and branches on independent tasks, then complete sessions. Copying upstream file selection alone does not solve this.
