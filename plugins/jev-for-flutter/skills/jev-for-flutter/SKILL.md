---
name: jev-for-flutter
description: Find Dart/Flutter code by describing a behaviour when its symbol name is unknown, or check a property across files without reading every file into the conversation. Use Jev for semantic searches; use Grep for an exact symbol.
---

# Jev for Flutter

Jev examines code outside this conversation and returns locations or selected source. It is a guide to the code, not an explanation or proof of completeness.

```bash
jev-flutter find "where the recorded audio is classified" lib/services
jev-flutter ask "does this retry a failed request?" lib/services
jev-flutter read "how cancellation is handled" lib/feature/screen.dart
jev-flutter status
```

Use `find` when the name is unknown or a lexical search failed. It screens every eligible file in the scope, checks the leading candidates against their source, then locates the useful blocks. If the scope exceeds 150 files it sends nothing: narrow the folder or explicitly raise `--max-files`. A `~` score is based on declarations only. Failed judgments and excluded files are reported. No match is not proof of absence.

Read the cited range, follow calls and data conversions, and check each part of the request before answering. Do not assume an interface covers every implementation. Use ordinary search for exact symbols and read the necessary source before editing.

Large Dart `Read` calls can be narrowed automatically. The note identifies the selected lines. Explicit `offset` or `limit` is always respected; repeating a whole-file Read retrieves the whole file. Broad requests, uncertain judgments and errors leave the Read unchanged. No file on disk is modified by selection.

`jev-flutter context "question" lib` also provides a map of related declarations. This is approximate syntax analysis, not resolved Dart types. Automatic preparation of this context is experimental and disabled by default; enable `context.enabled` only to evaluate it.

Jev runs only after per-project activation in `.claude/jev-for-flutter.json`. `jev-flutter doctor` checks configuration without a network call. Only run `jev-flutter init --enable-jev` when the user has authorized sending project code to TypeSafe. `--local` on `find`, `read` or `context` uses local ranking without an API call. User exclusions and source redaction apply to remote requests. A selected region can omit something relevant: recover the other ranges when needed.
