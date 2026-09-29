# Installing and using Jev for Flutter

This guide describes version 0.3.6. The repository, plugin and marketplace are named `jev-for-flutter`.

## Installation

This public repository provides its own marketplace. It is separate from Anthropic's official marketplace and requires no private GitHub access.

```bash
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
```

These commands install the plugin for your user. For the current project only, use `claude plugin install jev-for-flutter@jev-for-flutter --scope local`. See the [official Claude Code instructions](https://code.claude.com/docs/en/discover-plugins).

Requirements: Python 3.9+, macOS or Linux. Native Windows is unsupported. Precise Dart syntax outlines use the project's SDK and `package:analyzer`. If that parser is unavailable, the plugin continues with an approximate outline and labels it accordingly.

## Key and activation

Create a key in the TypeSafe console. Save it in a personal file, never in the repository:

```bash
mkdir -p ~/.config/jev-for-flutter
```

Use an editor to put only the key in `~/.config/jev-for-flutter/typesafe.key`, then restrict its permissions:

```bash
chmod 600 ~/.config/jev-for-flutter/typesafe.key
```

Alternatively, set `TYPESAFE_API_KEY` in Claude Code's environment. The file avoids entering a key in a command recorded by your shell history.

In each authorized project, `jev-flutter init --enable-jev` creates the configuration while preserving existing settings. You can also create `.claude/jev-for-flutter.json`, or merge this setting into it:

```json
{
  "jev": { "enabled": true }
}
```

Keep your other settings. Configuration precedence is `.claude/jev-for-flutter.json`, `.jev-for-flutter.json`, then the legacy `.claude/dartlens.json` and `.dartlens.json`. The first existing file is used. `~/.config/dartlens/typesafe.key` remains a fallback if no new key is available. Start a **new Claude Code session**, then run:

```text
! jev-flutter doctor
! jev-flutter status
```

The startup hook adds plugin executables to that session's command `PATH` through [`CLAUDE_ENV_FILE`](https://code.claude.com/docs/en/hooks#persist-environment-variables). It does not change your shell profile, so commands are not automatically available outside Claude.

To try a local checkout, run `claude --plugin-dir /path/to/jev-for-flutter/plugins/jev-for-flutter` from your project. Avoid loading both the installed and local copies.

## Everyday use

Ask Claude to work as usual. A full read of a Dart file with at least 400 lines can be narrowed to the question. A note identifies omitted lines. Repeating the Read retrieves the whole file; explicit `offset` or `limit` values are always respected. Broad requests, uncertainty, oversized files and errors leave the read unchanged.

If your prompt contains exactly one Dart file path, Jev can prepare this selection while Claude reasons. It does not search the repository to guess the file. The read reuses the result only when the question, file and model match, for at most 90 seconds. An in-progress preparation and the read share one Jev request. It counts toward the 24-request session cap even if Claude never reads the file. Disable preparation with `"read": {"prefetch": false}`.

Commands available in Claude's shell:

```bash
lens context "How is an empty response handled?" lib
lens context --local "response conversion" lib
lens "How is the selected area displayed?" lib/map_screen.dart
lens find "where a walk is saved after confirmation" lib/features
lens which -q "Does this widget contain a user-facing text literal?" lib/ui
lens --all "Read everything" lib/map_screen.dart
lens --local "selected area" lib/map_screen.dart
dart-outline lib/map_screen.dart
```

`lens` can also execute a command and filter its output: `lens "Why does the test fail?" -- flutter test test/example_test.dart`. The command really runs and its exit code is preserved. Complete output remains in a private local file for about 24 hours, cleaned up on subsequent uses.

`lens find` provides leads, not a complete flow. Above 150 files it sends nothing: choose a narrower directory or pass `--max-files N`. All eligible files in that scope are screened by Jev, with no keyword-based preselection. Text search remains appropriate for a known symbol.

Outlines are judged in groups of up to eight files to reduce requests; each file retains its own score. `"find": {"batch_files": 1}` restores individual requests. Search has a global 20-second network deadline. For an explicitly chosen large scope, increase it with, for example, `"jev": {"cli_timeout_s": 120}`. Files without judgments at the deadline are reported.

To try background context preparation, disabled by default after unfavorable results:

```json
{ "context": { "enabled": true } }
```

Preparation uses at most eight Jev requests per prompt, four concurrently, with no retries and a total cap of 24,000 **estimated** input tokens. The background process stops after eight seconds; an outage does not block Claude. Automatic delivery contains at most 8 KB of UTF-8 text. Identical questions and sources reuse scores for ten minutes. Changed files invalidate prepared context.

You can lower these limits:

```json
{ "context": { "max_requests": 4, "max_input_tokens": 12000, "max_chars": 8000 } }
```

`"lens": {"nudge": "off"}` disables automatic selection. `"nudge": "hint"` only suggests it. The default, `"nudge": "narrow"`, selects a range directly. `"nudge": "refuse_once"` keeps the old one-time refusal if desired; updates preserve explicit settings. The MCP tool `find_code`, now equivalent to `lens context`, is enabled separately with `"find": {"mcp": true}` and a new session. It remains off by default; automatic preparation does not depend on tool visibility.

## Conventions and memory

`/jev-for-flutter:rules` asks Claude to prepare `.claude/jev-for-flutter/rules.json` from your conventions. Review these rules: the guard gives probabilistic feedback on edits, not a replacement for lints or tests. Without the file, no rules are evaluated. This command uses the Claude conversation and may run Jev evaluations; it is not a free setup step.

The router works in the background with descriptions of the project's Claude memory entries and discovered skills. It suggests links rather than loading every entry. An arbitrary shared directory is not connected merely because it exists. Exact ticket-ID routing can work locally without Jev.

Disable these helpers independently with `"guard": {"enabled": false}` and `"router": {"enabled": false}`.

## Privacy

Enabling Jev allows the components to send relevant data to TypeSafe: excerpts or candidate contents, questions, edits and rules, and memory and skill descriptions. Masking recognizes some formats, not every possible secret. Enable the service only for code allowed to leave your machine.

In `~/.config/jev-for-flutter/policy.json`, exclude paths or Git remotes even when a project enables Jev:

```json
{
  "deny_paths": ["~/projects/confidential"],
  "deny_remotes": ["example.com/private-team/"]
}
```

These lists are personal; no specific customer repository is hardcoded. An unreadable policy blocks transmission. Paths are resolved before checking, including symlinks. Remotes use substring matching.

If activation is refused, the message names the policy file that actually contains the matching exclusion and its field (`deny_paths` or `deny_remotes`). A legacy policy still applies even when the new policy file does not exist.

To authorize one repository on an otherwise excluded Git host, add its **exact remote URL** to `allow_remotes` in the same personal policy:

```json
{
  "deny_remotes": ["git.example.com"],
  "allow_remotes": ["git@git.example.com:team/approved-project.git"]
}
```

This exception applies only to `deny_remotes` in that file. Other policies and `deny_paths` still take priority. The URL must match exactly, including its protocol and `.git` suffix. Other repositories on the host remain excluded. This does not activate Jev: run `jev-flutter init --enable-jev` separately in the approved project.

Without activation, or with `JEV_FLUTTER_JEV_DISABLE=1` in Claude's environment, `lens` search stays local and says so. No code context is automatically prepared. `JEV_FLUTTER_CONTEXT_DISABLE=1` disables only Jev calls and automation for `context`.

## Troubleshooting

- **Command not found:** start a new session after installation and check that the plugin and hooks are enabled. The `PATH` startup hook is needed in sessions without personal shell configuration.
- **Approximate outline:** the Dart parser is unavailable. The CLI may prepare it in the background on first use; `JEV_FLUTTER_OUTLINE_NO_BUILD=1` prevents this. The MCP server always sets that restriction. Preparation compiles the Dart helper and its dependencies, not your Flutter application.
- **Jev unavailable:** `lens` reports a local ranking. Relevance may differ; this does not prove that no other relevant code exists.
- **No context:** possible causes include a short request, slash command, deadline, no match, stale result or ended session. Inspect `context.jsonl` in the cache directory shown by `jev-flutter status`; `lens context --local "question" lib` diagnoses without Jev.
- **Reported cost:** Claude and Jev tokens are separate. Older Jev logs recorded input only, so complete billing cannot be inferred from them. `jev-flutter status` is a diagnostic, not an invoice.

## Migrating from dartlens 0.2

Remove the old version in its installation scope (`user` by default) before installing the new name, to avoid duplicate hooks:

```bash
claude plugin uninstall dartlens@dartlens
claude plugin marketplace remove dartlens
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
```

For a project-local installation, add `--scope local` to plugin commands. Legacy configurations, keys, rules and exclusions remain supported; the plugin moves or deletes nothing. Existing legacy cache paths remain in use. Old and new exclusion policies both apply, so migration drops no exclusion. Legacy environment variables remain recognized.

To stop using the old local directory names, close Claude sessions and rename `~/.config/dartlens` to `~/.config/jev-for-flutter`, and `~/.cache/dartlens` to `~/.cache/jev-for-flutter`, **only if each destination does not exist**. Keep every exclusion and the key file permissions. If both configuration directories exist, merge their exclusions before removing an old policy. Restart Claude after migration.

## Updating from Jev for Flutter 0.3.0

To replace the old marketplace address saved locally:

```bash
claude plugin marketplace remove jev-for-flutter
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
```

Restart Claude Code. Removing a marketplace can remove its plugins; the final command reinstalls this one under the same name. Your project settings and key stay in place.

[README](../README.md) · [Current benchmarks](PUBLIC-PROJECTS.md) · [Architecture](ARCHITECTURE.md)
