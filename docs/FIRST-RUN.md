# First-time setup

Jev for Flutter is a **Claude Code plugin**, not a `pubspec.yaml` dependency or an Android Studio or VS Code extension. Its code is [MIT licensed](../LICENSE). Claude Code and TypeSafe usage have separate pricing.

## Getting started

1. Install Python 3.9+ and Claude Code on macOS or Linux. On Windows, run both **inside WSL**; this plugin does not support native Windows. The Flutter SDK is optional. This release's installation was verified on macOS; WSL was not tested in this campaign.
2. Add the marketplace and install the plugin using the [README commands](../README.md#installation). This public repository provides its own marketplace; it is not part of Anthropic's official catalog. No private GitHub access is required.
3. Configure your TypeSafe key before launching Claude, or put it in the [personal key file](USAGE.md#key-and-activation). Do not paste it into a conversation or commit it to a repository.
4. Start a new Claude Code session at your project root. Run `! jev-flutter init --enable-jev`, then `! jev-flutter doctor`. Activation creates or merges `.claude/jev-for-flutter.json`, preserving other settings.
5. Work as usual. For a known method, name it and its file. For an unfamiliar behavior, describe what you are looking for. Install once, then enable Jev separately in each project you want it to process.

`doctor` makes no network calls and does not validate the key with TypeSafe. It checks key presence and local activation conditions. `jev-flutter status` shows limits, exclusions and logged usage.

## Common situations

| Situation | Behavior and next step |
|---|---|
| Missing key or activation | Reads remain unchanged. Use `find --local` for local search, or complete setup. |
| Rejected key, exhausted credit or unavailable network | Automatic reads stay complete; search reports fallback or missing judgments. Fix the key or service. Error cooldowns appear in `status`. |
| Small file | Files under 400 lines are not narrowed. Small projects do not receive an automatic saving. |
| File larger than 64 KB | Native reads stay unchanged. Request an explicit range if you know the relevant section. |
| Whole-file audit or refactor | The plugin should keep the full file. Focused reads target localized questions. |
| Insufficient excerpt | Read the file again in full, or request another explicit range. The original file on disk is unchanged. |
| Very large project | Narrow the search directory or explicitly increase `--max-files`. For a slow full search, adjust the [timeout](USAGE.md#everyday-use). |
| Multiple packages | Start Claude at the intended root. `doctor` shows the selected root; provide an explicit search scope. The plugin requires no particular `services`, `bloc` or `repository` layout. |
| Generated code | Known generated formats are excluded. Configure the `generated` list and directory markers for other generators. |
| No Dart SDK or approximate outline | The plugin works with an approximate parser. This is not resolved type analysis. `init` and `doctor` install no SDK. |
| Command not found in your terminal | The startup hook adds commands to Claude's session shell. Start a new session after installation and check that hooks are enabled. |
| Invalid JSON configuration | `init` refuses to overwrite it and `doctor` reports it. Fix the JSON before retrying. |
| Confidential project or team policy | Activation is per project. User exclusions take priority, including after migration, and prevent transmission. |
| Multiple plugin copies | Load either the marketplace copy or `--plugin-dir`. Remove the old installation before using the new one to avoid duplicate hooks. |
| Unused preparation | Naming a file can trigger a speculative request even if Claude never reads it. Disable `read.prefetch` if needed. |
| Upgrading from the old name | Legacy configurations, keys, rules, exclusions, environment variables and existing caches remain recognized. See [migration](USAGE.md#migrating-from-dartlens-02). |

The English and French search cases passed their rubric in this campaign. Other languages were not measured.

## Disable or uninstall

Set `jev.enabled` to `false` in the project configuration to disable Jev for that project. Setting `lens.nudge` to `off` disables only automatic read narrowing.

To remove a user-scoped installation:

```bash
claude plugin uninstall jev-for-flutter@jev-for-flutter
claude plugin marketplace remove jev-for-flutter
```

Add `--scope local` to the first command if that was the installation scope. Restart Claude. These commands do not remove your project files, rules, personal key or caches.

[Claude Code installation and WSL](https://code.claude.com/docs/en/setup) · [Official plugin reference](https://code.claude.com/docs/en/plugins-reference) · [TypeSafe pricing](https://docs.typesafe.ai/models)
