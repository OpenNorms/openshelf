# Changelog

All notable changes to the OpenShelf specification will be documented in this
file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the specification's versioning follows §10 of the spec: every change to
the specification is released as a new spec version and recorded here — a
minor version for backward-compatible changes, a major version for breaking
ones.

## [Unreleased]

### Added

- Release machinery for #10: a tag-triggered workflow builds the sdist and
  wheel, publishes to PyPI via trusted publishing (no stored tokens), and
  cuts a GitHub release; package metadata now carries the project URLs and
  the README documents the version policy (tool X.Y.Z implements spec X.Y).
  First publish waits on the one-time PyPI trusted-publisher setup.
- `openshelf lint` now validates a composing project's
  `.openshelf/relations.yaml` (§6.1): it schema-checks the overlay (whose
  endpoint pattern now accepts the `kb://uid:<uid>/...` form) and resolves
  every endpoint against the KBs and `uid`s recorded in `kbs.lock`,
  reporting dangling pages, unconnected KBs, and unrecorded `uid`s as
  project lint errors.

## [1.6] - 2026-11-02

### Changed

- **Publication moved to the OpenNorms organization.** The repository
  transferred from `hexsecs/openshelf` to `OpenNorms/openshelf` (the
  owner's decision; OpenShelf is OpenNorms' bootstrap document), and the
  canonical publication is now <https://opennorms.github.io/openshelf/>:
  the spec under `/spec/`, archives under `/spec/<version>/`, schemas
  under `/schemas/`, with the schemas' `$id`s updated to the new host.
  All `github.com` and git URLs for the repository redirect from the old
  location; the old Pages URLs do not redirect (GitHub does not redirect
  Pages on transfer) and are retired. No normative behavior changes.

## [1.5] - 2026-11-02

From #46: composition addressed KBs entirely by their self-asserted `id`
and never used the `uid`, leaving substitution (a different KB answering
to a familiar id) and rename (the same KB under a new id) both invisible
to tooling. Backward compatible: KBs without a `uid` compose as before.

### Added

- §6: identity verification in compositions. Sync records each connected
  KB's `uid` in kbs.lock; a later sync fails if the KB fetched under a
  connected id presents a different (or no) `uid` — a substitution — and
  fails if two connected KBs carry the same `uid`. A changed `id` with
  an unchanged `uid` is diagnosed as a rename, failing sync until the
  project updates the connection id.
- §6.1: overlay endpoints may address a KB by `uid`
  (`kb://uid:<uid>/<page-id>`), resolved against the lock, for assertions
  that must survive a rename.

### Changed

- §2: a composing project records and verifies KB `uid`s as a matter of
  course (was: MAY record, SHOULD flag duplicates).

## [1.4] - 2026-11-02

All items are from #41, a field report on adopting OpenShelf in an existing
wiki; all are backward compatible.

### Added

- §4.2/§2: content hashes for local sources — an optional `sha256` on
  `sources` entries (a mismatch is a lint error) and an optional
  `layout.checksums` manifest in sha256sum format that lint verifies,
  making §7's "raw sources are immutable" checkable.
- §4: sub-indexes may be declared with `type: index` frontmatter (a title,
  a "generated" marker, no summary needed); the no-frontmatter heuristic
  remains the fallback.
- §4.4: section addressing — `<page-id>#<heading-slug>` in both link
  styles and in `kb://` links, with the GitHub slug rule including the
  `-1`, `-2` dedup suffixes; lint flags fragments that match no heading.
  The MCP server's `read_page` accepts the form and returns the section.
- §4.4/§2: opt-in `unique-names: true` in kb.yaml — lint reports a
  duplicate page file name as an error when it appears.
- §4.1/§2: the uid adoption rule is now explicit — minting every uid once
  when an existing KB adopts the spec conforms — and tools SHOULD mint
  uids rather than the maintaining LLM. New `openshelf uid` command mints
  any missing KB and page uids; `openshelf init` mints the KB uid.
- §4.3: a type's declaration may be an object with `description` and
  `fields: {required: [...]}`; lint errors when a page is missing a field
  its type declares required. The plain-string form is unchanged.
- §8.4: standard callout names — `[!contradiction]`, `[!unverified]`,
  `[!stale]` — so tools can find them across KBs.

### Changed

- §2: a tool may keep its settings in its own file and reference it as
  `x-<tool>: {config: <path>}`.
- §10: changes SHOULD be batched into periodic releases rather than
  released one at a time.
- The examples are restamped to the current spec version and carry uids
  (minted with `openshelf uid`); they previously declared 0.1.

## [1.3] - 2026-11-02

### Added

- §2: an optional `visibility` field for kb.yaml (`public` | `internal` |
  `private`, default `public`). In §6, a non-public KB's L0 text, `use`
  hint, and paths MUST NOT be written into the committed
  `.openshelf/context.md`; they go to a gitignored
  `.openshelf/context.local.md` instead, or the tool refuses. `openshelf
  init --visibility` scaffolds the field and skips the CC-BY-4.0 license
  default for private KBs, and §2 notes SPDX `LicenseRef-<name>` for
  content that is not openly licensed (#37).
- §2: an optional `url` field for kb.yaml — the KB's published base URL.
  §6 sync records it in `kbs.lock`, and §4.4 renderers MAY use it as the
  target of a cross-KB link whose KB is not connected (#40).
- §4.4: the prefix shorthand `[[<kb-id>:<page-id>]]` for cross-KB
  wikilinks, valid only when the KB id is listed in `depends` (#40).

### Changed

- §4.2: `sources` entries MAY be plain strings — a string containing
  `://` is a URL, any other string is a path. Validators MUST grade
  schema findings by normative level: violations in REQUIRED fields are
  errors; shape problems in SHOULD or OPTIONAL fields are warnings (#38).
- §4.2: `sources[].path` is now defined — relative to the KB root, `/`
  separators, MUST NOT point outside the KB; lint checks that the cited
  file exists (#39).
- §4.4: cross-KB links are now defined in both link styles — Markdown
  `[label](kb://…)` and wikilink `[[kb://…|label]]` — and consumers MUST
  resolve both (#40).

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
