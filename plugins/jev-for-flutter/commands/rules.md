---
description: Generate or update convention-guard rules from project documentation (.claude/jev-for-flutter/rules.json)
argument-hint: "[topic or documentation file to prioritize]"
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(jev-flutter rules *), Bash(jev-flutter eval guard *)
---

Generate or update `.claude/jev-for-flutter/rules.json`, used by the Jev for Flutter convention guard. After edits, Jev evaluates each rule in the background; Claude receives a note only when a rule exceeds its threshold. $ARGUMENTS

## 1. Sources

Read existing `CLAUDE.md`, `AGENTS.md`, `.claude/*.md`, project skills (`.claude/skills/*/SKILL.md`, `.github/skills/*/SKILL.md`, `.agents/**/SKILL.md`) and project feedback memory entries. If the rules file already exists, start from it: preserve IDs and report any removed rule.

Also read `analysis_options.yaml`, its `include` package, `linter: rules:` and any DCM configuration.

## 2. Selection

Keep a convention only if all three conditions hold:

1. **Checkable from one edit:** the changed text and about 25 surrounding lines suffice. Exclude rules requiring other files, Git history, execution or a project-wide view.
2. **Semantic:** checking it requires understanding code intent. A text search or regex alone should not need Jev.
3. **Not covered by a lint:** check active rules, included lint packages and DCM first. If uncertain, look up the relevant lint in the included file. A deterministic lint does not need a probabilistic judge. `jev-flutter rules check` detects overlap with active lints and includes, but not DCM.

Aim for 10–30 clear rules rather than many vague ones.

## 3. Format

```json
{
  "version": 1,
  "defaults": {"threshold": 0.85, "applies_to": ["lib/**/*.dart"]},
  "rules": [
    {
      "id": "no-hardcoded-ui-text",
      "question": "Does the change add a user-visible text literal in a widget instead of a localized string?",
      "true": "A string literal shown to the user is introduced in widget code",
      "false": "Visible text comes from the localization API, or the literal is not user-visible (keys, logs, tests)",
      "applies_to": ["lib/ui/**/*.dart"],
      "message": "Use the project's localization API for user-visible text.",
      "examples": [
        {"after": "Text('My dogs')", "violation": true},
        {"after": "Text(context.l10n.dogsTitle)", "violation": false},
        {"after": "debugPrint('dogs loaded');", "context": "Future<void> _load() async {", "violation": false}
      ]
    }
  ]
}
```

For each rule:

- `id`: stable, unique kebab-case.
- `question`: English, atomic yes/no, where **YES means a violation**. Ask what “the change” introduces. Jev receives numbered `change`, `after_context`, and detected enclosing declarations in `enclosing`.
- `true` / `false`: short, contrasting English meanings, including exceptions.
- `applies_to`: the narrowest practical globs relative to the root, such as `lib/ui/**/*.dart` or `test/**/*_test.dart`. Omission uses `defaults.applies_to`.
- `threshold`: only when it differs from `defaults.threshold`.
- `message`: one actionable line in the project's preferred language, English by default. This is what Claude will read.
- `examples`: two to four short realistic cases, with at least one violation and one compliant example. Add `context` when needed. Use no secrets or confidential code: questions and examples are sent to Jev.

## 4. Checks

Run `jev-flutter rules check` and fix every error. Address each warning or explain it briefly.

If Jev is available, `jev-flutter rules test <file.dart> --change '<before>' '<after>'` can check one or two cases. `--state` shows the exact guard payload. `jev-flutter eval guard --from-rules --sweep` reports precision and recall on the examples; these optimistic figures have no relevance on a fake server. Both commands make Jev calls with the guard deadline and no retry. A failed case represents a silent guard.

## 5. Report

Show a table of IDs, messages, `applies_to` and source documentation sections. Summarize excluded conventions and reasons: existing lint, insufficient context or nonsemantic rule. Remind the user that the guard requires project `jev.enabled: true` and no user-policy exclusion. Do not change activation or policy.
