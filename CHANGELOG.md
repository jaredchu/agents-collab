# Changelog

## v0.2.0-preview.1 · 2026-11-28

- Add opt-in `auto` for delegated writers and reviewers. Bounded one-file
  assignments use Medium. Broader or ambiguous assignments use High.
- Change delegated `inherit` to use the active lead's captured effort. To retain
  the old delegate behavior, use `interface-default`. The host lead can keep
  `inherit`.
- Record the concrete effort separately from the chosen policy and check it
  against dispatch receipts. Continue to use the optional v0.1.1 Rust backend.

[Experimental prerelease notes and profile migration](docs/releases/v0.2.0-preview.1.md)

## v0.1.1 · 2026-11-23

- Harden private task storage and recheck registered output destinations.
- Render sealed review packets for Claude CLI and clarify recovery after
  quota interruptions and partial helper failures.

[Release notes](docs/releases/v0.1.1.md)

## v0.1.0 · 2026-11-21

- Publish the first experimental skill package and optional macOS arm64 CLI.

[GitHub release](https://github.com/jaredchu/agents-collab/releases/tag/v0.1.0)
