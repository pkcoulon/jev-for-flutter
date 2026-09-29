<div align="center">

# Jev for Flutter

**Find the right Dart code. Keep Claude's context focused.**

A Claude Code plugin powered by [Jev](https://typesafe.ai).

[Install](#installation) · [Benchmarks](docs/PUBLIC-PROJECTS.md) · [Guide](docs/USAGE.md) · [MIT](LICENSE)

</div>

Jev selects relevant passages from large Dart files before Claude reads them. Full files remain accessible.

- **Automatic focused reads** during your usual Claude workflow.
- **Search by description**, with batched file screening and source verification.
- **Parallel preparation** while Claude reasons, when your prompt names a file.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/public-read-results-dark.svg">
  <img alt="Three targeted questions on Flutter Form App, LocalSend and AppFlowy: 23% fewer Claude tokens, 53% lower Claude plus Jev cost, 7% longer runtime. Accepted answers: 3/3 with Jev, 2/3 without." src="docs/img/public-read-results-light.svg" width="960">
</picture>

Three known-file questions, one run per variant. Large files account for the savings; the small file shows no benefit. **These results do not establish savings on completed development tasks.** [Method, results and limitations](docs/PUBLIC-PROJECTS.md).

Batched search also took **74% less time on LocalSend and 82% less on AppFlowy** than individual requests. All 12 search cases passed the same rubric in both variants.

## Installation

Requires Claude Code, Python 3.9+, macOS or Linux, and a [TypeSafe API key](https://typesafe.ai).

```bash
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
export TYPESAFE_API_KEY="your-typesafe-key"
```

Start a new Claude Code session in your Flutter project, then enable Jev:

```text
! jev-flutter init --enable-jev
! jev-flutter doctor
```

Enable it separately in each project. This allows the plugin to send relevant code and questions to TypeSafe. `doctor` checks your local setup without paid calls. Then work with Claude as usual.

**MIT licensed.** Claude and TypeSafe usage are billed separately. [Setup, troubleshooting and uninstalling](docs/FIRST-RUN.md).
