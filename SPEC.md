# OpenShelf Specification — v1.5

OpenShelf standardizes the **LLM Wiki** pattern described by Andrej Karpathy
([gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)).
In that pattern, an LLM incrementally builds and maintains a persistent,
interlinked set of Markdown pages between you and your raw sources, instead of
re-deriving everything from the sources at query time.

The gist is deliberately abstract, and people organize their wikis in very
different ways. OpenShelf keeps that freedom. It standardizes only what another
tool or project needs in order to **connect** to a KB:

- **The contract (§2–§6)** is small and strict. It says where things are, how
  pages are identified and summarized, and how links work. Every conforming KB
  meets it, so any number of KBs can be connected to one project.
- **The conventions (§7–§9)** are recommendations: a default layout, page
  types, operations and profiles. Follow them, change them or ignore them; a
  KB stays compatible as long as it meets the contract.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this
document are to be interpreted as described in BCP 14 [RFC 2119] [RFC 8174]
when, and only when, they appear in all capitals, as shown here. They are
normative only in the contract sections (Part I); the convention sections
(Part II) are non-normative unless a KB opts into a profile (§9), in which
case that profile's key words carry the same force as Part I for that KB.

This specification and its schemas are published at
<https://hexsecs.github.io/openshelf/>: the current spec under `/spec/`, each
release archived under `/spec/<version>/`, and the schemas under `/schemas/`
— the schemas' `$id`s are those published URLs.

---

## 1. Design principles

1. **Declare, don't dictate.** A KB says in its manifest where its pages,
   index and sources are. Consumers read the manifest instead of assuming a
   layout.
2. **Progressive context.** Every KB offers the same tiers of detail (§3), so
   an agent connected to many KBs loads only as much as a task needs.
3. **Plain files.** Markdown with YAML frontmatter in a directory, usually a
   git repository. Readable without tools, and works in Obsidian.

---

# Part I — Compatibility contract

## 2. Manifest — `kb.yaml`

A KB is a directory with a `kb.yaml` file at its root. This file is the only
fixed path in the spec.

```yaml
openshelf: "1.5"                 # REQUIRED  spec version
id: awesome-can-bus           # REQUIRED  [a-z0-9-], unique per publisher
uid: 0193f8c2-7a1b-7c3d-8e4f-5a6b7c8d9e0f  # SHOULD  UUID, minted once, never changes
title: Awesome CAN bus        # REQUIRED
description: >                # REQUIRED  L0 text, ≤ 300 chars
  Curated tools and libraries for working with CAN bus...

layout:                       # OPTIONAL  where things are; defaults shown
  pages: wiki                 #   directory holding pages (searched recursively)
  index: index.md             #   L1 entry point
  sources: raw                #   raw sources, if kept in the KB
  schema: AGENTS.md           #   instructions for the maintainer LLM
  log: log.md                 #   activity log
  checksums: raw/MANIFEST.sha256  # OPTIONAL  sha256sum-format manifest lint verifies

types: {}                     # OPTIONAL  custom page types, see §4.3
profile: wiki                 # OPTIONAL  see §9
version: 2026.10.31           # OPTIONAL
license: CC-BY-4.0            # SHOULD    SPDX id for the content; CC-BY-4.0 recommended
maintainers: [hexsecs]        # SHOULD
tags: [can, automotive]       # OPTIONAL
depends: []                   # OPTIONAL  ids of KBs this one links into
visibility: public            # OPTIONAL  public | internal | private; default public
url: https://example.org/kb/  # OPTIONAL  published base URL of this KB, see §4.4
unique-names: false           # OPTIONAL  when true, duplicate page file names are lint errors, see §4.4
```

If `license` is absent, consumers MUST NOT assume one. `openshelf init` uses
CC-BY-4.0 unless told otherwise. Content that is not openly licensed MAY
carry an SPDX `LicenseRef-<name>` identifier instead of a standard SPDX id.
`openshelf init` MUST skip the CC-BY-4.0 default when `--visibility private`
is given: private content is not openly licensed by default, so no license
is claimed for it.

`visibility` says who a KB may be shared with: `public` (anyone), `internal`
(a bounded group, such as one organization), or `private` (its owner only).
It is OPTIONAL and defaults to `public`. The value is the KB's own
declaration, and tools MUST honour it when they connect the KB to a project
(§6): a non-public KB's L0 text and paths are exactly the kind of thing that
would otherwise be copied into a project's committed files without anyone
deciding to share them.

A KB MAY declare its published base `url` — the canonical site where the KB
is rendered, if it has one. Cross-KB links use it as a fallback target when
the KB is not connected (§4.4), and a project MAY record it in
`.openshelf/kbs.lock` alongside the pinned revision.

A KB SHOULD also carry a `uid`: a UUID minted once, when the KB is created,
and never changed afterwards — the same rule as a page's `uid` (§4.1), one
level up. The `id` names the KB for humans and registries; the `uid`
identifies it across renames, repository moves, and `id` changes. A mirror of
a KB keeps its `uid` — it is the same KB, replicated; a fork that diverges is
a new KB and MUST be minted a fresh `uid`. A project that connects KBs (§6)
records it in `.openshelf/kbs.lock` alongside the pinned revision and
verifies it on sync (§6): the `uid`, not the `id`, is what proves a
composition imported the KB it meant to. Tools SHOULD mint a KB's `uid`,
as they do page `uid`s (§4.1).

All `layout` paths are relative to the KB root and MUST NOT point outside it.
Consumers MUST use the declared paths and the defaults above for any that
are missing. `layout.pages` MAY be `.` for a KB whose pages sit at the root.

A KB MAY declare `layout.checksums`: a file in `sha256sum` format listing
content hashes of files in the KB — typically its raw sources, which §7
holds immutable. Lint MUST verify a declared manifest: a listed file that
is missing, or whose hash does not match, is an error.

Fields not defined here are allowed and MUST be ignored by consumers that
don't understand them. Tool-specific settings SHOULD go under an `x-<tool>`
key. A tool MAY keep sizeable settings in its own file and reference it
from its key — `x-<tool>: {config: <path>}`, the path relative to the KB
root.

Schema: [`schemas/kb.schema.json`](schemas/kb.schema.json).

## 3. Context tiers

| Tier | Comes from               | Budget (guide)          | When it is loaded                  |
|------|--------------------------|-------------------------|------------------------------------|
| L0   | `description`            | ≤ 300 characters        | Always, for every connected KB     |
| L1   | `layout.index`           | ≤ 4,000 tokens          | When a task touches the KB's scope |
| L2   | a page                   | ≤ 2,500 tokens per page (by `depth`, §4.5) | When that page is relevant         |
| L3   | `layout.sources` or URLs | unbounded               | Only to verify or extend a page    |

Consumers MUST be able to work from L0 alone and MUST NOT load L1+ of a KB
just because it is connected. Producers SHOULD respect the budgets.

## 4. Pages

A **page** is any `.md` file under `layout.pages`, except:

- the files declared as `layout.index`, `layout.schema` and `layout.log`,
  and anything under `layout.sources`;
- sub-indexes: files declared with `type: index` in their frontmatter, and
  — as a fallback for undeclared ones — files with no frontmatter that are
  linked from the index (or from another sub-index) and that themselves
  contain links. A declared sub-index SHOULD carry a `title`; it needs no
  `summary`, and the page rules below do not apply to it;
- files and directories whose name starts with `_` or `.`. Directories inside
`layout.pages` are free-form: a KB MAY organize them by type, topic, date, or
not at all.

### 4.1 Identity

A page's **id** is its path relative to `layout.pages`, without `.md`, using
`/` as the separator: `entities/python-can`, or just `python-can` in a flat
layout. Ids are what links and other KBs use, so renaming or moving a page
SHOULD leave a redirect (§4.4).

A page SHOULD also carry a persistent **`uid`** in its frontmatter (§4.2): a
UUID minted once, when the page first enters a KB, and never changed
afterwards. The path id says where the page lives today; the `uid` identifies
the page itself, across renames, moves within a KB, and moves between KBs —
a genuine move keeps its `uid`. Copying a page's content into another KB
creates a new page, which MUST be minted a fresh `uid`; only a move preserves
one. Tooling that creates pages (ingesters, scaffolders) MUST mint the `uid`
at creation and preserve it verbatim on every rewrite, exactly as it does
`created`: set once, never regenerated. Consumers MUST treat the `uid` as an
opaque string; any UUID version is valid, and UUIDv7 is RECOMMENDED for new
pages because it sorts by creation time. A `uid` is not a content hash: it
does not change when the page's content does.

Minting a `uid` for every existing page once, when a KB adopts this
specification, and preserving each from then on, conforms to the minting
rule: for an adopted KB, the minting event is the adoption. Tools SHOULD do
the minting (`openshelf uid` does, for pages and for the KB itself, §2)
rather than the maintaining LLM: a UUID an LLM writes from memory is not
reliably random, and a patterned or colliding `uid` is worse than a late
one.

Cross-KB references (§4.4, §6.1) MAY cite a page by `uid` so they survive
renames; consumers MUST resolve a `uid` through an index of `uid` → current
location built at sync or composition time. If two pages in one composition
carry the same `uid`, they are the same page appearing twice — a move in
flight, or a copy that kept a `uid` it should not have — and composition
tooling SHOULD flag it.

### 4.2 Frontmatter

Pages MUST have YAML frontmatter with these fields:

| Field     | Rule                                                              |
|-----------|-------------------------------------------------------------------|
| `title`   | REQUIRED                                                          |
| `summary` | REQUIRED, ≤ 160 chars, one sentence; what the index and search show |

And SHOULD have:

| Field     | Rule                                                              |
|-----------|-------------------------------------------------------------------|
| `uid`     | Persistent page identifier (UUID); minted once at creation; MUST NOT change, see §4.1 |
| `type`    | A page type, see §4.3                                             |
| `created` | Date the page first entered the KB (`YYYY-MM-DD`); set once; MUST NOT change |
| `updated` | Date of last substantive change (`YYYY-MM-DD`)                    |
| `depth`   | How much authored depth the page carries, see §4.5                |
| `sources` | List of `{url or path, retrieved}` backing the page's claims, or plain strings (below) |

Any other fields (`tags`, `aliases`, `related`, Dataview fields, profile
fields) MAY be present; consumers MUST ignore fields they do not understand.

A `sources` entry MAY be a plain string instead of an object: a string
containing `://` is shorthand for `{url: <string>}`, and any other string
is shorthand for `{path: <string>}`. Consumers MUST accept both forms. A
`path` — in either form — is relative to the KB root, uses `/` separators,
and MUST NOT point outside the KB: the same rule as §2's `layout` paths, so
a citation stays valid when the page moves. Lint SHOULD check that a cited
path exists. A path entry MAY also carry a `sha256`, the content hash of
the cited file — for a local source the useful integrity fact, where
`retrieved` is the one for a URL — and lint MUST report a mismatch as an
error.

Validators MUST grade schema findings by the field's normative level: a
violation in a REQUIRED field (`title`, `summary`, `redirect`) is an error,
while a shape problem in a SHOULD or OPTIONAL field is a warning. The
schema is the contract for the required core; advisory fields must not make
an otherwise conforming page fail.

Schema: [`schemas/page.schema.json`](schemas/page.schema.json).

### 4.3 Page types

`type` is free text, so a KB MAY use whatever types suit its domain. The
**core types** in §8.2 have shared meanings, and a KB SHOULD use them where
they fit. A KB that uses other types SHOULD declare them in `kb.yaml`, so
consumers and other maintainers know what they mean:

```yaml
types:
  decision: A choice that was made, with the alternatives and the reasoning.
  recipe: Step-by-step instructions for one task.
```

A type's value MAY instead be an object with a `description` and declared
`fields`:

```yaml
types:
  meeting:
    description: Digested minutes of one meeting.
    fields: {required: [date, attendees]}
```

Lint MUST report a page that is missing a field its type declares required
as an error: the KB opted into the rule by declaring it. The plain-string
form stays valid and declares no fields.

### 4.4 Links

Inside a KB, pages MAY use either style; consumers MUST resolve both:

- **Markdown links** with relative paths: `[cantools](cantools.md)`.
- **Wikilinks**: `[[cantools]]`, `[[entities/cantools]]` or
  `[[cantools|label]]`. Consumers MUST resolve a wikilink to the page whose
  id matches; if none does, to the only page with that file name; otherwise
  the wikilink is ambiguous and lint SHOULD flag it.

Links **to another KB** MUST use `kb://<kb-id>/<page-id>`, in either link
style: as a Markdown link, `[label](kb://other-kb/concepts/foo)`, or as a
wikilink, `[[kb://other-kb/concepts/foo|label]]`. Consumers MUST resolve
both forms. A wikilink MAY instead use the prefix shorthand
`[[<kb-id>:<page-id>]]`, which means exactly `kb://<kb-id>/<page-id>`; the
shorthand is valid only when `<kb-id>` is listed in the linking KB's
`depends`, so it cannot be confused with a local page whose name contains
a colon. Lint SHOULD flag a shorthand-shaped wikilink whose prefix is not
listed in `depends`.

Consumers MUST resolve a cross-KB link only when that KB is connected.
When it is not, a renderer MUST show the link text — unless the target
KB's published base `url` (§2) is known, for example from `kbs.lock`, in
which case the renderer MAY link to `<url>/<page-id>` instead.

A link MAY address a section of a page: `<page-id>#<heading-slug>` in
either link style, and `kb://<kb-id>/<page-id>#<heading-slug>` across KBs.
The slug is the GitHub heading slug: the heading text lowercased, with
punctuation other than hyphens and underscores removed and spaces replaced
by hyphens; a repeated heading takes a `-1`, `-2`, … suffix. Consumers
that read pages by section — as §4.5 assumes for `deep` pages — MUST
accept this form, and tools and APIs MUST treat it as addressing that
section. Lint SHOULD flag a fragment that matches no heading in the
target page.

Because a bare file-name wikilink resolves only while the name is unique,
adding a same-named page in another folder silently makes existing links
ambiguous. A KB MAY set `unique-names: true` in `kb.yaml`; lint MUST then
report a duplicate page file name as an error when it appears, instead of
warnings later on every link that uses the name.

A moved page MAY leave a stub at its old path with `redirect: <new-id>` in its
frontmatter and no body. Consumers MUST follow it.

### 4.5 Page depth

A page MAY carry a `depth` field saying how much authored depth it has.
Depth is the L2 sizing ladder: it tells consumers how much context a page
will cost before they load it, and it gives maintainers a shared language
for how far a page has been taken. There are four depths:

| Depth   | Budget (guide)   | What it is |
|---------|------------------|------------|
| `stub`  | ≤ 750 tokens     | Machine-generated placeholder: title, summary, link, provenance. No authored content. |
| `brief` | ≤ 750 tokens     | The shortest authored page: a verified orientation — what it is, who it is for, key caveats, checked links. |
| `full`  | ≤ 2,500 tokens   | The standard researched page: what it is, how it works, where it fits, limits, status and sources. |
| `deep`  | ≤ 6,000 tokens   | A rare, selective research-grade treatment of a landmark topic, assigned deliberately — never the default. |

The design choices behind the four:

- **`stub` reserves the address.** Ingest generates a stub for every known
  item, so every link target exists and is reachable from the index from
  day one. A stub is not a reading tier; its size is bounded by its
  template, and lint applies the `brief` ceiling as a sanity cap — a stub
  that has grown authored content is misclassified and SHOULD be promoted,
  not left to swell.
- **`brief` is sized to one retrieval chunk.** Retrieval practice puts a
  coherent, self-contained chunk at roughly 400–800 tokens, so a 750-token
  brief page is retrievable and loadable whole. It exists for pointer-type
  entries (a book, a dataset, a conference) where a full treatment would
  be padding — the page earns its place by being *verified*, not long.
  Brief is not the summary layer: the `summary` field (≤ 160 chars) stays
  the one-line orientation in indexes and search results.
- **`full` is anchored to a complete single-topic article.** At ~1,900
  words it sits near the 90th percentile of Wikipedia articles — enough
  for mechanism, evidence and limits without splitting the topic. The
  budget rose from the original flat L2 budget of 2,000 tokens because
  real researched pages kept hitting that ceiling and losing load-bearing
  detail to budget-trimming. Full pages are slightly heavy for bulk agent
  loading (distilled context is usually 1,000–2,000 tokens), so consumers
  SHOULD load them one at a time, or by section — the ladder assumes
  section-level retrieval exists for L2.
- **`deep` is an overview ceiling, not a monograph.** At ~4,500 words it
  is large enough to hold a landmark topic's apparatus — the primary
  numbers, the design trade-offs, the contested points — that a `full`
  page demonstrably loses. It is also too large for routine loading:
  6,000 tokens would consume most of a typical always-on context budget,
  so consumers MUST NOT load `deep` pages wholesale by default; they are
  on-demand, read through a table of contents or by section. A topic that
  outgrows `deep` splits, Wikipedia-style, into a `deep` overview plus
  linked `full` and `brief` children rather than growing one page
  further.
- **Promotion is editorial, not volumetric.** A page moves stub → brief →
  full → deep when the topic earns it — centrality, citations from other
  pages, a maintainer's judgment that the substance is being lost — not
  merely because text accumulated. Most pages SHOULD never be `deep`;
  if everything is deep, the ladder carries no signal.
- **Absent `depth`, the `full` budget applies.** Depth is OPTIONAL; a KB
  that never uses it sees one change, the default L2 budget of 2,500
  tokens. If `depth` is absent, consumers MUST apply the `full` budget. Any
  other `depth` value is invalid: consumers MUST NOT apply a budget for it
  (the `full` budget applies) and validators MUST flag it — as a warning,
  per §4.2's severity rule for OPTIONAL fields.

Dates in frontmatter are deliberately three distinct facts: `created`
(when the page first entered the KB; set once, never changes), `updated`
(when its content last substantively changed) and — in the `awesome`
profile — `last_checked` (when the listed thing's `url` and `status` were
last verified). A page can be old, recently edited and stale-checked, or
any other combination; conflating the three hides exactly the freshness
signal each is meant to carry.

## 5. Index

`layout.index` is the L1 entry point and the first thing an agent reads after
L0. It is Markdown, organized however the KB likes, but:

- Every page MUST be reachable from it, either directly or through
  sub-indexes it links to. Lint SHOULD report pages that aren't.
- Each page link SHOULD be followed by that page's `summary`, so the index
  works as a catalog without opening pages.
- If the KB is too large for the L1 budget, the index SHOULD link to
  sub-indexes (for example one per category) rather than list every page.

The index MAY be written by hand, by the LLM, or generated from frontmatter.

## 6. Connecting KBs to a project

A project lists its KBs in `.openshelf/kbs.yaml`:

```yaml
openshelf: "1.5"
kbs:
  - id: awesome-can-bus
    source: github:hexsecs/awesome-can-bus   # github:owner/repo, git URL, or local path
    ref: main                                # branch, tag or commit
    path: .                                  # OPTIONAL, subdirectory holding kb.yaml
    use: when the task involves CAN tooling  # OPTIONAL, hint shown with the L0 text
```

The `id` MUST match the KB's own `kb.yaml` id. KB ids MUST be unique within a
project.

A tool (CLI, MCP server or agent hook) then:

1. MUST fetch each KB into `.openshelf/cache/<id>/` (gitignored), pinned in
   `.openshelf/kbs.lock`.
2. MUST write `.openshelf/context.md`: one block per public KB with its L0
   text, the `use` hint, and the resolved path of its index.
3. The project's `AGENTS.md` / `CLAUDE.md` MUST include or link
   `.openshelf/context.md`, so the agent always sees L0 for every KB and knows
   how to go deeper.

`context.md` is a committed file, so a connected KB whose `visibility` (§2)
is not `public` MUST NOT have its L0 text, `use` hint, or paths written
into it. A tool MUST either write that KB's block to a gitignored file —
`.openshelf/context.local.md`, which the tool MUST add to
`.openshelf/.gitignore` and which `context.md` points to by KB id only — or
refuse to connect the KB, telling the user why. A KB's visibility is its
owner's declaration; connecting a KB MUST NOT silently publish it.

A project MUST treat connected KBs as read-only. Knowledge gained while
working on the project MUST be contributed back to a KB through that KB's own
maintenance process, in its own repository.

Identity in a composition is the `uid` (§2), not the `id`: the `id` is the
address `kb://` links use, and the `uid` is what proves the KB at that
address is the KB that was connected.

- When a project syncs, it MUST record the `uid` of every connected KB
  that declares one in `kbs.lock`, alongside the pin.
- On a later sync, if the KB fetched under a connected `id` presents a
  different `uid` from the one the lock records — or none — the sync MUST
  fail: a different KB is answering to a familiar name, and composing it
  silently is never right. Replacing a KB deliberately is done by
  removing the connection and adding the new KB, which records its `uid`
  fresh.
- Two KBs carrying the same `uid` MUST NOT be composed together — that
  is the same KB connected twice, or a fork that failed to mint a fresh
  `uid` (§2) — and sync MUST fail on it.
- If the KB fetched under a connected `id` declares a different `id` but
  the same `uid` as the lock records, it is the same KB renamed. Sync
  MUST fail with that diagnosis until the project updates the connection
  `id`: the `uid` proves it is a rename rather than a substitution, and
  references use the `id`, so the rename stays a deliberate act by the
  project.
- A KB that declares no `uid` composes as before, unverified.

Projects MAY connect a KB as a git submodule or plain directory instead; the
cache is just the default.

Schema: [`schemas/project.schema.json`](schemas/project.schema.json).

### 6.1 Relation overlays

A project that connects more than one KB composes them. A composing project
MAY assert relations between pages — across connected KBs, or within one —
**without modifying any KB**, using a relation overlay: a data file that lives
in the composing project (conventionally `.openshelf/relations.yaml`), never
in a KB.

```yaml
relations:
  - from: kb://awesome-kb-automotive-security/can-fd
    to: kb://awesome-kb-embedded-security/can-tools
    type: related
    note: "Protocol view in one KB, tooling view in the other."
```

- Endpoints MUST be `kb://` URIs (§4.4), so an overlay never depends on a
  KB's internal file layout.
- An endpoint MAY address a KB by `uid` instead of `id` —
  `kb://uid:<uid>/<page-id>` — for an assertion that must survive a
  rename of that KB; consumers MUST resolve the `uid` form against the
  `uid`s recorded in `kbs.lock`. The `uid` form is for overlays: page
  bodies and `depends` keep using `id`s.
- Defined types: `related` and `same-as` are symmetric; `broader` and
  `narrower` are inverses; `supersedes` is directional. Projects MAY use
  further types; consumers MUST ignore types they do not recognise, and MUST
  ignore fields they do not recognise.
- Consumers that compose (build-time renderers, context builders) MUST
  validate every endpoint against the revisions pinned in
  `.openshelf/kbs.lock`. Consumers MUST treat an endpoint that does not
  resolve at the pinned commit as an error in the composing project — never
  as a lint failure in the referenced KB.
- Overlay relations MUST remain distinguishable from relations a page asserts
  in its own frontmatter (`related:`): their provenance is the composition,
  not the KB. Consumers SHOULD present them labelled as such.
- A symmetric relation SHOULD be presented from both endpoints, even though
  the overlay records it once.
- `same-as` records that two pages describe the same entity, for the composed
  view only. Consumers MUST NOT merge the pages: each MUST still render on
  its own, in its own KB, and a KB's standalone rendering MUST be unaffected
  by any overlay.
- A KB MAY later adopt an overlay relation into its own pages through its
  normal maintenance process; the overlay entry SHOULD then be removed, so a
  relation lives in exactly one layer at a time.
- Tooling MAY propose candidate relations — for example pages in different
  KBs sharing a canonical URL, a DOI, or a title — but a candidate becomes a
  relation only when it is recorded in the overlay.

Schema: [`schemas/relations.schema.json`](schemas/relations.schema.json).

---

# Part II — Conventions

Nothing in this part is required for compatibility.

## 7. Default layout

This layout follows the gist's three layers, and is what the `layout`
defaults point to:

```
my-kb/
├── kb.yaml          manifest
├── AGENTS.md        schema: conventions and workflows for the maintainer LLM
├── index.md         catalog of pages
├── log.md           append-only activity log
├── wiki/            LLM-maintained pages
└── raw/             immutable sources; raw/assets/ for images
```

| Gist layer  | Default location | Notes                                               |
|-------------|------------------|-----------------------------------------------------|
| Raw sources | `raw/`           | The LLM reads but never modifies them. They MAY live outside the KB (cited by URL) when they can't be redistributed. A `layout.checksums` manifest (§2) makes the immutability verifiable. |
| Wiki        | `wiki/`, `index.md`, `log.md` | Written by the LLM, read by people.    |
| Schema      | `AGENTS.md`      | `CLAUDE.md` works too. Co-evolved by human and LLM. |

Inside `wiki/`, a flat directory is simplest. Larger KBs often use
`wiki/entities/`, `wiki/concepts/` and so on; ids then include the folder.

## 8. Maintenance

### 8.1 Operations

The gist defines three operations. A KB's schema file describes how it runs
them, and SHOULD use these names so tools can trigger them:

| Operation | Input                    | Typical effect |
|-----------|--------------------------|----------------|
| `ingest`  | a source (file/URL/text) | Keep it in sources if allowed; write a `source` page; update every affected page (one source often touches 10–15); update the index; log it. One at a time with the human reviewing, or in batches. |
| `query`   | a question               | Read the index, then relevant pages, then sources if needed; answer with citations. File useful answers back as `answer` pages, so explorations compound. |
| `lint`    | —                        | Check the contract (§2–§5), contradictions, stale claims, orphan and unreachable pages, missing concept pages, missing cross-references, broken links, budgets, and gaps worth filling. |

### 8.2 Core page types

From the gist, plus `answer`:

| `type`       | Purpose                                                        |
|--------------|----------------------------------------------------------------|
| `overview`   | Overview of the KB or a large area of it                       |
| `source`     | Summary of one raw source                                      |
| `entity`     | A concrete thing: tool, person, organization, product, paper   |
| `concept`    | An idea, technique or term                                     |
| `comparison` | Side-by-side of several entities or concepts                   |
| `synthesis`  | Conclusions drawn across many sources                          |
| `answer`     | A query answer filed back into the KB                          |

### 8.3 Log format

The gist suggests a heading per entry, so the log can be parsed with standard
Unix tools:

```markdown
## [2026-10-31] ingest | python-can PyPI page
Created python-can; updated socketcan and the index.
```

### 8.4 Content

- Pages SHOULD state contradictions between sources on the page instead of
  silently picking one.
- Claims no source backs SHOULD be marked, e.g. `(unverified)`.
- Contradictions, unverified claims and possibly stale claims SHOULD be
  marked with the standard callouts — `> [!contradiction]`,
  `> [!unverified]`, `> [!stale]` (Obsidian callout syntax) — so tools can
  find them across KBs.
- Pages that outgrow the L2 budget SHOULD be split.

### 8.5 Tooling

The format needs nothing beyond an LLM agent and a text editor. The gist
suggests:

- **Search** once the index alone isn't enough, for example
  [qmd](https://github.com/tobi/qmd) (hybrid BM25/vector search, CLI and MCP)
  or a small custom script.
- **Obsidian** for reading (graph view shows hubs and orphans), Obsidian Web
  Clipper for turning articles into Markdown sources, and Dataview for
  querying frontmatter.
- **git** for history and collaboration.

## 9. Profiles

A profile is a named set of extra rules for a common kind of KB. A KB opts in
with `profile:` in `kb.yaml`. Opting in makes the profile's rules binding for
that KB, so tools can rely on them; the contract in Part I is unchanged.

### 9.1 `wiki` (default)

No extra rules.

### 9.2 `awesome` — replacing awesome lists

Each listed item is a page with `type: entity`, which MUST also have:

```yaml
url: https://github.com/...    # the thing being listed
category: Libraries            # used to group the index
```

and SHOULD have:

```yaml
license: MIT                   # SPDX id of the thing being listed
status: active                 # active | maintenance | archived | published | unknown
last_checked: 2026-10-31       # when url and status were last verified
created: 2026-10-31            # when the entry first entered the KB (set by ingest, then preserved)
depth: full                    # how far the entry has been deepened (§4.5)
```

`status` describes the listed thing's maintenance state. For a finished
work — a publication such as a paper, talk, or book — the status MUST be
`published`: the work is complete, it has no maintenance state to track,
and `published` says so as a fact rather than leaving the field at the
unverified default. `unknown` MUST be reserved for living resources
(projects, tools, services) whose current state has not been verified.

The index MUST group entities by `category`, one line each with the summary,
so it still reads as a classic awesome list. What this adds over a flat list:

- Each entry has an LLM-written summary, comparison links and sources.
- Adding an entry is an `ingest`: a contributor submits a URL, the
  maintainer LLM writes or updates the page, links it to related entries and
  updates the index.
- `lint` MUST recheck `url`, `status` and `last_checked`, and MUST flag dead
  or archived entries.

## 10. Versioning

This spec uses `openshelf: "<major>.<minor>"`. Version 1.0 is the first
stable version. From 1.0 on:

- A **minor** version MUST NOT break compatibility: a KB that conforms to
  1.x remains conforming under every later 1.y, and consumers MUST accept
  KBs declaring any earlier minor version of the same major version.
- A **major** version MAY break compatibility.
- Before 1.0, minor versions could break compatibility; a KB declaring
  `openshelf: "0.1"` predates the stable contract.

Every change to this specification MUST be released as a new spec version —
a minor version for a backward-compatible change, a major version for a
breaking one — and MUST be recorded in
[`CHANGELOG.md`](CHANGELOG.md), which follows the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. A change
with no version bump and no changelog entry is not a released change, and
consumers are entitled to ignore it. Changes SHOULD be batched into
periodic releases rather than released one at a time, so consumers can
follow the specification by following its releases.
