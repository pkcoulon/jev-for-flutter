# Preparing context while Claude works

> Historical design. Version 0.3 uses native focused reads and keeps automatic context optional. See the [current measurements](PUBLIC-PROJECTS.md) and [architecture](ARCHITECTURE.md).

September 29, 2026: local implementation by Codex, unpublished at the time. Version 0.2 measurements do not measure this redesign.

## Problem addressed

Earlier trials showed that Claude could ignore the search tool, or stop at screens without inspecting the service layer. Reducing text or the cost of an incomplete answer does not meet the product objective.

This design prepares context automatically, alongside Claude, and adds local references to search results. It does not require discovering `find_code` or encountering a refusal first. Oversized declarations retain their file and line references rather than disappearing from the ranking.

## Implementation

- Shared engine for `lens context`, the automatic hook and optional MCP tool.
- Local declaration/reference index updated by fingerprint, without builds or embeddings.
- Per-file Jev ranking, at most four concurrent requests per prompt and eight total, without retries.
- One delivery to the parent or subagent, without waiting in the collection hook.
- Cancellation of queued requests, worker deadlines, local fallback and stale-source rejection.
- Unrestricted reading by default, with the old refusal available explicitly. Conventions and memory retained; router made asynchronous.

## Offline checks

The temporary script and data remain in `~/.cache/dartlens-bench/context-redesign-2026-09-29/`. Checks use a fake server, without real keys or builds; they do not measure Jev's semantic relevance. [Later real sessions](CONTEXT-RESULTS.md) are accounted separately within the authorized $5 budget.

**41 checks pass**, covering limits, concurrency, cache, source changes, exclusions, symlinks, PEM secrets, fallback, hooks, cancellation, superseded requests, subagent delivery and MCP. Already-sent requests from successive prompts can overlap; the four-request concurrency cap applies per prompt.

On the pinned Pioudex copy, **local search without Jev** includes these declarations in its map:

| Part of the flow | Visible source |
|---|---|
| Response interpretation | `ConfidenceTier`, `Identification.fromJson` |
| Listening and display decision | `ListenSession._verdict` |
| Photo and display decision | `PhotoSession` |
| Embedded processing | `EmbeddedBirdIdentifier` |
| Server fallback | `RepliBirdIdentifier` |

Context now fits within **8,000 UTF-8 bytes**. The long embedded-processing body is referenced by range rather than copied in full. Finding that symbol fixes visibility, not necessarily Claude's reading or reasoning. Archived scores from eight Pioudex Jev requests were replayed offline to check the compact format.

## Remaining measurement questions

The intended gain comes from avoided searches and parallel work. Irrelevant extra context could instead increase tokens. Initial real sessions confirm delivery to parent and subagent, but their answers remain incomplete. The [real results](CONTEXT-RESULTS.md) separate answer-quality failures from the subsequently fixed transport issue.

Comparisons preserve prompts and check complete branches before comparing tokens, combined Claude + Jev cost and time through verification. Historical Pioudex cases are regression checks, not general validation on unknown projects.

[Architecture and limits](ARCHITECTURE.md) · [Usage](USAGE.md) · [Earlier data](EXPERIMENT-5USD.md)
