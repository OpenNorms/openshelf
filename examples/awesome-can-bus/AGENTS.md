# Schema for this KB

This is an OpenShelf knowledge base using the `awesome` profile (see OpenShelf `SPEC.md` v1.0). It follows the LLM Wiki pattern: `raw/` holds immutable sources, `wiki/` is maintained by you, and this file holds the conventions. The human and the LLM refine this file together over time.

## Conventions
- Every listed tool, library or product is a `type: entity` page with `url`, `category`, `status` and `last_checked`.
- Explanations of underlying technology are `type: concept` pages; head-to-heads are `type: comparison`.
- Categories in use: Libraries. Add new categories only when an entry fits none of these.
- Sources here are public web pages cited by URL; nothing is copied into `raw/`.

## ingest <url or text>
1. Read the source and tell the human the key takeaways before writing.
2. If an entity for the thing already exists, update it; otherwise create `wiki/<id>.md`.
3. Update every other affected page, and add `related` links in both directions.
4. Cite every claim in `sources`. Never invent facts, versions or licenses; if a source doesn't say it, leave the field out.
5. Regenerate `index.md` from frontmatter, grouped by `category`, with concepts last.
6. Append `## [YYYY-MM-DD] ingest | <source title>` to `log.md`.

## query <question>
Read `index.md`, then the relevant pages. Answer with links to pages. If the answer would be useful again, file it as a `type: answer` page and log it.

## lint
Check frontmatter against the OpenShelf schemas, broken links, orphan pages, contradictions between pages, entities whose `last_checked` is older than 90 days, dead or archived URLs, and pages over 2,000 tokens. Report, fix, and log.
