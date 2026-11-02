# OpenShelf

An open standard for the **LLM Wiki** pattern described by [Andrej Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): an LLM builds and maintains a persistent, interlinked Markdown wiki from your raw sources, so knowledge is compiled once and kept current instead of re-derived on every query.

Think of each knowledge base as a book on a project's shelf. An agent sees every spine (a one-line description), opens the table of contents (the index) when a task touches that subject, reads only the pages it needs, and checks the references (raw sources) when it has to.

The gist leaves layout, page formats and tooling open, and OpenShelf keeps it that way. It standardizes only what's needed to **connect** knowledge bases, and leaves everything else to the KB's owner:

- **A small contract.** A `kb.yaml` manifest at the root declares the KB's description and where its pages, index and sources are. Pages need only a `title` and a one-line `summary`, and are identified by their path. Links can be Markdown or Obsidian wikilinks; links into other KBs use `kb://<kb>/<page>`.
- **Free organization.** Folders, page types, naming and workflows are up to you. The spec offers conventions from the gist (default layout, page types, ingest/query/lint, log format) that you can adopt, adapt or ignore.
- **Progressive context.** Every KB offers the same four tiers: a one-line description (L0), the index (L1), pages (L2) and raw sources (L3). Agents load only as deep as the task needs, so a project can connect many KBs cheaply.
- **Connect many KBs to a project.** List them in `.openshelf/kbs.yaml`; tooling turns that into a short `context.md` the project's agent always sees.
- **Awesome lists, upgraded.** The opt-in `awesome` profile makes each list entry a sourced, cross-linked page that an LLM keeps current, while the index still reads as a classic awesome list.

## Contents

- [`SPEC.md`](SPEC.md): the v1.0 spec
- [`schemas/`](schemas/): JSON Schemas for `kb.yaml`, page frontmatter and `.openshelf/kbs.yaml`
- [`src/openshelf/`](src/openshelf/): the `openshelf` command-line tool
- [`examples/awesome-can-bus/`](examples/awesome-can-bus/): a small awesome-profile KB using the default layout
- [`examples/openshelf-design/`](examples/openshelf-design/): a KB with its own layout (nested folders, wikilinks, a custom page type)
- [`examples/project/`](examples/project/): a project that connects both

## Tooling

The `openshelf` command (Python 3.10+) works with any KB that meets the spec:

```sh
pip install git+https://github.com/hexsecs/openshelf

openshelf init my-kb --description "One line saying what this KB covers."   # new KB, default layout, CC-BY-4.0
openshelf lint my-kb                                    # check it against the spec

cd my-project
openshelf add github:someone/some-kb --use "when the task involves X"        # connect a KB
openshelf sync                                          # fetch KBs, write .openshelf/kbs.lock and .openshelf/context.md
```

Point your project's `AGENTS.md` or `CLAUDE.md` at `.openshelf/context.md`. `openshelf sync --locked` reproduces the exact commits in the lock file.

### MCP server

`openshelf mcp` serves a project's connected KBs to any MCP client over stdio, one tier at a time:

| Tool | Tier | What it returns |
|---|---|---|
| `list_kbs` | L0 | Every KB's id, title, one-line description and `use` hint |
| `read_index(kb, subindex?)` | L1 | The KB's index (or a sub-index) and the pages it links to |
| `read_page(kb, page)` | L2 | One page's frontmatter, body and resolved links, following redirects |
| `read_source(kb, path)` | L3 | A raw source file, restricted to the KB's sources directory |
| `search(query, kb?)` | — | Matching pages with their summaries |

It is read-only and re-reads the files on every call, so edits show up without a restart. Links come back resolved, including `kb://` links into other KBs. Install it with the `mcp` extra and add it to Claude Code from your project directory:

```sh
pip install "openshelf[mcp] @ git+https://github.com/hexsecs/openshelf"
claude mcp add --scope project openshelf -- openshelf mcp
```

Other clients take the same command, `openshelf mcp`, run from the project directory (or pass `--project <dir>`).

## Status

Draft. See the [roadmap](https://github.com/hexsecs/openshelf/issues/2) for what's next.

## License

- **Code** (`src/`, `tests/`, `schemas/`, CI): [MIT](LICENSE).
- **Specification and examples** (`SPEC.md`, `examples/`): [CC-BY-4.0](LICENSE-SPEC).

Knowledge bases you create are yours to license. `openshelf init` defaults to CC-BY-4.0, which you can change with `--license`.
