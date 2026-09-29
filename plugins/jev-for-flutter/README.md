# Jev for Flutter

Find the right Dart code and keep Claude's context focused. This community plugin uses [Jev by TypeSafe](https://typesafe.ai) to select relevant passages from large Dart files and search code by description. Claude can still read full files whenever needed.

- Focused reads work during ordinary Claude Code sessions.
- Semantic search screens files in batches, then verifies the leading candidates against their source.
- Naming a Dart file lets the plugin prepare its selection while Claude reasons.

Built for **Claude Code on macOS or Linux**, with Python 3.9+. A TypeSafe API key is required for Jev calls. The plugin is [MIT licensed](LICENSE); Claude and TypeSafe usage are billed separately. This is a Claude Code plugin, not a Dart package or an official TypeSafe or Google product.

## Install and enable

```bash
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
```

Configure a TypeSafe key using the [setup guide](https://github.com/pkcoulon/jev-for-flutter/blob/main/docs/FIRST-RUN.md), then start a new Claude Code session in your project:

```text
! jev-flutter init --enable-jev
! jev-flutter doctor
```

Enable Jev once per project. The diagnostic checks local settings without network calls. Excluded projects remain blocked unless their personal policy is updated explicitly.

## What runs and what is sent

The plugin runs bundled Python hooks and commands locally, adds its commands to the session shell path, and exposes an optional local MCP search tool. After project activation, relevant code and questions are sent to `https://api.typesafe.ai`. Enabled convention and memory helpers can also send rules, edits, and memory or skill descriptions. Known secret formats are masked, but masking cannot detect every secret.

Local caches can contain code outlines, prepared excerpts, prompt-related state and usage logs. Some results expire for reuse; this is not a guarantee that their files are deleted. See the [privacy and configuration guide](https://github.com/pkcoulon/jev-for-flutter/blob/main/docs/USAGE.md#privacy). TypeSafe handles submitted data under its own terms.

The optional Dart outline helper can fetch its dependencies through Dart's configured package source and compile locally. Set `JEV_FLUTTER_OUTLINE_NO_BUILD=1` to keep approximate parsing instead. No Flutter application build is required.

## Evidence

[Public benchmarks](https://github.com/pkcoulon/jev-for-flutter/blob/main/docs/PUBLIC-PROJECTS.md) cover Flutter Form App, LocalSend and AppFlowy. They distinguish search speed from complete Claude responses. Small samples do not establish universal savings or unchanged quality on completed development tasks.

[Usage and troubleshooting](https://github.com/pkcoulon/jev-for-flutter/blob/main/docs/USAGE.md) · [Report an issue](https://github.com/pkcoulon/jev-for-flutter/issues) · [Third-party notices](THIRD_PARTY_NOTICES.md)
