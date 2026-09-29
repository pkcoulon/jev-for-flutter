<div align="center">

# Jev for Flutter

<p>
  <a href="https://typesafe.ai">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/img/brands/typesafe-dark.png">
      <img src="docs/img/brands/typesafe-light.png" alt="TypeSafe, creators of Jev" height="26">
    </picture>
  </a>
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://flutter.dev">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/img/brands/flutter-dark.svg">
      <img src="docs/img/brands/flutter-light.svg" alt="Flutter" height="26">
    </picture>
  </a>
</p>

**Give Claude the Dart code it needs.**

Focused reads and code search for Flutter, powered by [Jev](https://typesafe.ai).

[Install](#installation) · [Results](#results) · [Guide](docs/USAGE.md) · [MIT](LICENSE)

</div>

Claude can read hundreds of lines to understand one method. Jev selects the relevant passage before that code enters Claude's conversation. Keep working as usual; the plugin handles the selection.

[![Animated explanation: in the recorded AppFlowy read, Jev selected 64 of 1,667 lines, preserving the requested method. Full files remain accessible.](docs/img/focused-read-demo.gif)](docs/DEMO.md)

*Animation of a recorded AppFlowy read, with illustrative timing. [Video](docs/img/focused-read-demo.mp4) · [Source and accessible still](docs/DEMO.md).*

## What you get

- **Focused reads, automatically.** Relevant Dart excerpts with original line numbers. Claude can still request the full file.
- **Search by intent.** Describe a behavior with `jev-flutter find` to find files and lines, even when you do not know the symbol name.
- **Preparation in parallel.** Name a Dart file in your prompt and Jev can prepare the read while Claude reasons.

## Installation

Requires Claude Code, Python 3.9+, macOS or Linux, and a [TypeSafe API key](https://typesafe.ai).

```bash
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
```

Set your key in the shell that launches Claude, or use the [persistent key file](docs/USAGE.md#key-and-activation):

```bash
export TYPESAFE_API_KEY="your-typesafe-key"
```

Start a new Claude Code session in your Flutter project, then enable it:

```text
! jev-flutter init --enable-jev
! jev-flutter doctor
```

Install once; enable once per project. Activation allows relevant code and questions to be sent to TypeSafe. `doctor` checks local setup without paid calls. [Setup and troubleshooting](docs/FIRST-RUN.md).

## Results

Three paired questions on **Flutter Form App, LocalSend and AppFlowy**:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/public-read-results-dark.svg">
  <img alt="Three targeted questions: 23% fewer Claude tokens, 53% lower Claude plus Jev cost, 7% longer runtime. Accepted answers: 3/3 with Jev, 2/3 without." src="docs/img/public-read-results-light.svg" width="960">
</picture>

One run per question and variant, reviewed without blinding. Large files account for the savings; the small file shows no benefit. **This measures targeted questions, not completed development tasks or guaranteed savings.**

Separately, batched search took **74% less time on LocalSend and 82% less on AppFlowy** than individual requests, with all 12 search cases passing in both versions. [Data, method and limitations](docs/PUBLIC-PROJECTS.md).

**MIT licensed.** Claude and TypeSafe usage are billed separately. [Privacy](docs/USAGE.md#privacy) · [License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md).

<sub>Flutter and the related logo are trademarks of Google LLC. We are not endorsed by or affiliated with Google LLC.</sub>
