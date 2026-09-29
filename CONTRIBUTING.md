# Contributing to Jev for Flutter

The plugin lives in `plugins/jev-for-flutter`, with its Python package in `lib/jev_flutter`. It requires Python 3.9+ on macOS or Linux, with no third-party Python runtime dependencies. The Dart helper is optional.

Before proposing a change:

```bash
python3 -m compileall -q plugins/jev-for-flutter/lib plugins/jev-for-flutter/hooks plugins/jev-for-flutter/mcp
python3 plugins/jev-for-flutter/bin/jev-flutter --help
python3 bench/run.py --check-tasks
claude plugin validate .
claude plugin validate plugins/jev-for-flutter
```

These commands make no Jev calls or LLM sessions. Campaign scripts can: set a budget before running them. Do not include keys, confidential source code or personal transcripts in contributions.

Report retrieval relevance, final-answer quality, Claude tokens, Jev tokens, combined cost and duration separately. Include failures in totals. A shorter selection or lower cost is not a benefit if the answer is incomplete.

Charts are generated from the JSON files in `docs/` using `docs/readme_charts.py` and Matplotlib 3.9.4. Keep them readable in light and dark themes. The packaged `LICENSE` and `THIRD_PARTY_NOTICES.md` must match their copies at the repository root.

Public documentation and chart labels use English. Preserve the original language of recorded benchmark prompts and answers.

[Architecture](docs/ARCHITECTURE.md) · [Public benchmark protocol and results](docs/PUBLIC-PROJECTS.md) · [MIT license](LICENSE)
