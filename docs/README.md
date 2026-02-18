# Documentation Index

This repository keeps all maintained docs under `docs/`.

## Current docs

- `docs/changelog.md`: project change history.
- `docs/reference/design-guidelines.md`: architecture and implementation rules.
- `docs/reference/proj-analyser.md`: project-level analysis component guide.

## Generated outputs

Generated reports are written under `docs/generated/` and are git-ignored by default.

- `docs/generated/file/`: single-file analysis outputs.
- `docs/generated/project/`: project-level analysis outputs.

## Historical docs

Archived drafts and old proposals are kept in `docs/archive/` for context only.

- `docs/archive/codex_spec.md`
- `docs/archive/performance_patterns_proposal.md`

## Runtime file policy

User-specific runtime files are excluded from git.

- `uploads/deepseek_config.json`: local user config (ignored).
- `uploads/deepseek_config.example.json`: tracked template.
- `uploads/*`: uploads and generated export files (ignored by default).
