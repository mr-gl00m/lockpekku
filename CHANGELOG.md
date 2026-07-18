# Changelog

All notable changes to this project will be documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-07-18

First public release. Versions 0.1 and 0.2 were internal.

### Highlights
- Finds the processes that block a folder move or rename on Windows: an executable running from inside the tree, a working directory inside the tree, or a command line naming a path inside it.
- Probe Move proves whether a folder can actually move right now, catching the raw handles (Explorer windows, preview pane, search indexer, elevated processes) that no process scan can attribute.
- Review table with live refresh; kill one process at a time or clear everything at once.

### Added
- Process scan across three lock vectors (exe, cwd, cmdline) with per-row reason and locked path.
- Live refresh every 2.5 s that preserves checkbox selections; toggleable from the toolbar.
- Kill flow: confirmation dialog, graceful terminate with a 3 s escalation to hard kill, per-process outcomes, elevation hint when access is denied.
- Probe Move: non-mutating delete-sharing check across the tree (bounded at 25,000 entries).
- Copy Report: the current scan as a markdown table on the clipboard, ready for Discord.
- Amber woodpecker icon and phosphor terminal theme (near-black, hard edges, `#ffb000`).

### Security
- Command lines containing secret-shaped options (`--password`, `--token`, `--api-key`, and similar) are redacted in the table and in copied reports.
- Copied reports escape markdown and mention injection before reaching the clipboard.
- Kill targets are guarded against pid reuse: process identity is verified by creation time before terminate.
- Network and device roots are refused; scan roots resolve before path matching.
- Logs write to `%LOCALAPPDATA%\Lockpekku\logs`. No telemetry, no network calls.

[0.3.0]: https://github.com/mr-gl00m/lockpekku/releases/tag/v0.3.0
[Unreleased]: https://github.com/mr-gl00m/lockpekku/compare/v0.3.0...HEAD
