# Changelog

## 0.3.4 — 2026-09-30

- Show the actual exclusion policy file and matching field when activation is refused, including legacy configurations.
- Keep exclusions from both policy locations effective and report unreadable policies without naming a different file.
- Add official TypeSafe and Flutter brand assets to the README, with light and dark variants.

## 0.3.3 — 2026-09-29

- Publish the repository under MIT with English documentation, benchmark reports and chart labels.
- Simplify the README and translate the convention-rules command; generated messages follow the project language.
- Remove absolute local source paths from exported results and ignore common secret files.
- No changes to the search or read-selection engines; measurements remain those of 0.3.2.

## 0.3.2 — 2026-09-29

- Batch up to eight file outlines per request, retaining a separate score for each file. Fewer Jev requests and tokens, measured on Flutter Form App, LocalSend and AppFlowy.
- Shorter reads for explicitly named methods, preserving the full declaration and detected local dependencies.
- Fix method-boundary protection, exclude generated `*.mapper.dart` files, and check generation markers without rescanning the repository.
- Rename the package to `plugins/jev-for-flutter` and the Python module to `jev_flutter`. Preserve compatibility for configurations, keys, rules, caches, exclusions and legacy environment variables.
- Add `jev-flutter init --enable-jev` and `jev-flutter doctor` for first-time setup. Include the MIT license and attribution in the installed package.
- Simplify the README and charts. Report search and Claude-answer measurements separately, without claiming universal savings.

## 0.3.1 — 2026-09-29

Prepare reads in parallel when the prompt names a single Dart file. Reuse the result within the same session, without a second request, with expiration and invalidation.

## 0.3.0 — 2026-09-29

Focused native reads, the Jev for Flutter marketplace, and on-demand semantic search. Experimental automatic context remains disabled by default.
