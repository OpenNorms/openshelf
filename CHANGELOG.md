# Changelog

All notable changes to the OpenShelf specification will be documented in this
file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the specification's versioning follows §10 of the spec: every change to
the specification is released as a new spec version and recorded here — a
minor version for backward-compatible changes, a major version for breaking
ones.

## [Unreleased]

## [1.2] - 2026-11-02

### Changed

- The specification and its schemas are published at
  <https://hexsecs.github.io/openshelf/>: the current spec under `/spec/`,
  each release archived under `/spec/<version>/`, and the schemas under
  `/schemas/`. The schemas' `$id`s are now those published URLs (they
  previously pointed at `github.com` URLs that did not resolve to the JSON).
- The repository is renamed `hexsecs/openkb` → `hexsecs/openshelf`, matching
  the name the schemas and README always used; the old URLs redirect.

## [1.1] - 2026-11-02

### Added

- This changelog. §10 now requires every change to the specification to bump
  the spec version and add an entry here, so the spec's history is a release
  history rather than a commit log.

## [1.0] - 2026-11-02

The first stable version. Includes the changes merged since 0.1 (PRs #29–#33),
first released together as 1.0, plus the specification-language pass (#34).

### Added

- Page depth tiers — `stub` / `brief` / `full` / `deep` budgets — and the
  `created` frontmatter date (§4.5). (#29)
- `status: published` for finished works in the `awesome` profile; `unknown`
  reserved for unverified living resources (§9.2). (#30)
- Relation overlays: a composing project can assert relations between pages
  across (or within) KBs without modifying any KB (§6.1), with
  `schemas/relations.schema.json`. (#31)
- Page `uid`: a persistent UUID identifier, minted once and never changed,
  independent of the page's path (§4.1, §4.2). (#32)
- KB `uid`: the same persistent identifier for the KB itself (§2). (#33)

### Changed

- The whole specification is written in BCP 14 specification language
  (RFC 2119 / RFC 8174); requirements previously stated in plain prose are
  now MUST / SHOULD / MAY statements. (#34)
- §10 versioning policy: from 1.0, a minor version MUST NOT break
  compatibility. The spec is no longer a draft.

## [0.1] - 2026-10-31

### Added

- Initial draft: the `kb.yaml` manifest, context tiers, pages and
  frontmatter, the index, connecting KBs to a project, default layout and
  maintenance conventions, and the `wiki` and `awesome` profiles — with JSON
  schemas, examples, and the reference CLI (`init` / `lint` / `add` / `sync`)
  and MCP server.
