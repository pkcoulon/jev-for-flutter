# Preparing reads while Claude reasons

Version 0.3.1 starts Jev analysis in the background when a prompt names one eligible Dart file. Claude can reuse the selection when it reads. Jev questions, thresholds and window sizes are unchanged.

## Real checks on September 29, 2026

The three files from the [0.3.0 read campaign](READ-RESULTS.md) were each tested once in both modes using real Jev: analysis at read time, then an already-prepared selection. The order was reversed for the second file.

| File | Analysis at read time | Selection already prepared | Same passage |
|---|---:|---:|---|
| Notifications | 545 ms | 92 ms | Yes |
| Sync caches | 522 ms | 118 ms | Yes |
| Audio identification | 551 ms | 130 ms | Yes |
| **Mean** | **539 ms** | **114 ms** | **3/3** |

This table measures the read hook, including Python startup. **Waiting at this point falls by 79% across these three cases.** Preparation itself took 455–533 ms, outside that duration: work happens earlier rather than disappearing. If Claude reads too early, it waits for the remainder of the same request, with no duplicate call. This does not apply without an explicit path.

An additional Claude Sonnet 5 session checked the complete integration on the audio question: selection ready about three seconds before Read, confirmed reuse, a single read, and the expected method present. The engine took 33 ms within the read hook. The answer covers all four existing criteria after Astra's source review, without an independent reviewer. Claude reported 9.053 seconds and $0.047921.

This campaign does not compare complete answers with and without preparation. **It establishes neither 79% faster overall answers nor additional token or cost savings.** At publication, the README percentages still came from the separately identified 0.3.0 campaign. Unused preparation can add a Jev request.

## Checks and budget

- Selection requests match those archived for 0.3.0; probabilistic responses may vary. All three resulting windows match across modes.
- 27 additional checks with a simulated HTTP server: concurrent reads, deduplication, expiration, changed source/question/model, withdrawn activation, shared budget, errors, external links, overly broad results and full-file recovery.
- All 69 existing read and optional-context checks pass. No builds or simulators.
- Real validation adds eight Jev calls and one Claude session: **$0.05110**, including $0.00317 Jev. Historical cumulative budget at this stage: **$3.48515 of $5**.

The plan, frozen plugin and traces remain in the private `~/.cache/dartlens-bench/read-prefetch-2026-09-29/` archive. [Data, answers and criteria](prefetch-results.json). The published engine matches the tested snapshot.

[Architecture](ARCHITECTURE.md) · [Installation and settings](USAGE.md) · [README](../README.md)
