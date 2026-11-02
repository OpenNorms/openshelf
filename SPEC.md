# OpenShelf Specification — v0.1 (draft)

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

The key words MUST, SHOULD and MAY are used as in RFC 2119. They apply only
in the contract sections; the convention sections are non-normative unless a
KB opts into a profile (§9).

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
openshelf: "0.1"                 # REQUIRED  spec version
id: awesome-can-bus           # REQUIRED  [a-z0-9-], unique per publisher
title: Awesome CAN bus        # REQUIRED
description: >                # REQUIRED  L0 text, ≤ 300 chars
  Curated tools and libraries for working with CAN bus...

layout:                       # OPTIONAL  where things are; defaults shown
  pages: wiki                 #   directory holding pages (searched recursively)
  index: index.md             #   L1 entry point
  sources: raw                #   raw sources, if kept in the KB
  schema: AGENTS.md           #   instructions for the maintainer LLM
  log: log.md                 #   activity log

types: {}                     # OPTIONAL  custom page types, see §4.3
profile: wiki                 # OPTIONAL  see §9
version: 2026.10.31           # OPTIONAL
license: CC-BY-4.0            # SHOULD    SPDX id for the content; CC-BY-4.0 recommended
maintainers: [hexsecs]        # SHOULD
tags: [can, automotive]       # OPTIONAL
depends: []                   # OPTIONAL  ids of KBs this one links into
```

If `license` is absent, consumers MUST NOT assume one. `openshelf init` uses
CC-BY-4.0 unless told otherwise.

All `layout` paths are relative to the KB root and MUST NOT point outside it.
Consumers MUST use the declared paths and the defaults above for any that
are missing. `layout.pages` MAY be `.` for a KB whose pages sit at the root.

Fields not defined here are allowed and MUST be ignored by consumers that
don't understand them. Tool-specific settings SHOULD go under an `x-<tool>`
key.

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
- sub-indexes: files with no frontmatter that are linked from the index (or
  from another sub-index) and that themselves contain links;
- files and directories whose name starts with `_` or `.`. Directories inside
`layout.pages` are free-form: organize by type, topic, date or not at all.

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

Cross-KB references (§4.4, §6.1) MAY cite a page by `uid` so they survive
renames; consumers resolve a `uid` through an index of `uid` → current
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
| `uid`     | Persistent page identifier (UUID); minted once at creation, never changes, see §4.1 |
| `type`    | A page type, see §4.3                                             |
| `created` | Date the page first entered the KB (`YYYY-MM-DD`); set once, never changes |
| `updated` | Date of last substantive change (`YYYY-MM-DD`)                    |
| `depth`   | How much authored depth the page carries, see §4.5                |
| `sources` | List of `{url or path, retrieved}` backing the page's claims      |

Any other fields (`tags`, `aliases`, `related`, Dataview fields, profile
fields) are allowed and ignored by consumers that don't understand them.

Schema: [`schemas/page.schema.json`](schemas/page.schema.json).

### 4.3 Page types

`type` is free text, so a KB can use whatever types suit its domain. The
**core types** in §8.2 have shared meanings, and a KB SHOULD use them where
they fit. A KB that uses other types SHOULD declare them in `kb.yaml`, so
consumers and other maintainers know what they mean:

```yaml
types:
  decision: A choice that was made, with the alternatives and the reasoning.
  recipe: Step-by-step instructions for one task.
```

### 4.4 Links

Inside a KB, pages MAY use either style; consumers MUST resolve both:

- **Markdown links** with relative paths: `[cantools](cantools.md)`.
- **Wikilinks**: `[[cantools]]`, `[[entities/cantools]]` or
  `[[cantools|label]]`. A wikilink resolves to the page whose id matches; if
  none does, to the only page with that file name; otherwise it is ambiguous
  and lint SHOULD flag it.

Links **to another KB** use `kb://<kb-id>/<page-id>`. Consumers resolve them
only when that KB is connected, and otherwise show the link text.

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
  that has grown authored content is misclassified and should be promoted,
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
  should load them one at a time, or by section — the ladder assumes
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
  merely because text accumulated. Most pages should never be `deep`;
  if everything is deep, the ladder carries no signal.
- **Absent `depth`, the `full` budget applies.** Depth is optional; a KB
  that never uses it sees one change, the default L2 budget of 2,500
  tokens. Any other `depth` value is a schema error.

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
openshelf: "0.1"
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

1. Fetches each KB into `.openshelf/cache/<id>/` (gitignored), pinned in
   `.openshelf/kbs.lock`.
2. Writes `.openshelf/context.md`: one block per KB with its L0 text, the `use`
   hint, and the resolved path of its index.
3. The project's `AGENTS.md` / `CLAUDE.md` includes or links
   `.openshelf/context.md`, so the agent always sees L0 for every KB and knows
   how to go deeper.

Connected KBs are read-only from the project's side. Knowledge gained while
working on the project goes back to a KB through that KB's own maintenance
process, in its own repository.

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
- Defined types: `related` and `same-as` are symmetric; `broader` and
  `narrower` are inverses; `supersedes` is directional. Projects MAY use
  further types; consumers MUST ignore types they do not recognise, and MUST
  ignore fields they do not recognise.
- Consumers that compose (build-time renderers, context builders) MUST
  validate every endpoint against the revisions pinned in
  `.openshelf/kbs.lock`. An endpoint that does not resolve at the pinned
  commit is an error in the composing project — never a lint failure in the
  referenced KB.
- Overlay relations MUST remain distinguishable from relations a page asserts
  in its own frontmatter (`related:`): their provenance is the composition,
  not the KB. Consumers SHOULD present them labelled as such.
- A symmetric relation SHOULD be presented from both endpoints, even though
  the overlay records it once.
- `same-as` records that two pages describe the same entity, for the composed
  view only. It does not merge the pages: each still renders on its own, in
  its own KB, and a KB's standalone rendering is unaffected by any overlay.
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
| Raw sources | `raw/`           | The LLM reads but never modifies them. They MAY live outside the KB (cited by URL) when they can't be redistributed. |
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

- State contradictions between sources on the page instead of silently
  picking one.
- Mark claims no source backs, e.g. `(unverified)`.
- Split pages that outgrow the L2 budget.

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
work — a publication such as a paper, talk, or book — the status is
`published`: the work is complete, it has no maintenance state to track,
and `published` says so as a fact rather than leaving the field at the
unverified default. `unknown` is reserved for living resources (projects,
tools, services) whose current state has not been verified.

The index groups entities by `category`, one line each with the summary, so
it still reads as a classic awesome list. What this adds over a flat list:

- Each entry has an LLM-written summary, comparison links and sources.
- Adding an entry is an `ingest`: a contributor submits a URL, the
  maintainer LLM writes or updates the page, links it to related entries and
  updates the index.
- `lint` rechecks `url`, `status` and `last_checked`, and flags dead or
  archived entries.

## 10. Versioning

This spec uses `openshelf: "<major>.<minor>"`. Before 1.0, minor versions may
break compatibility.
