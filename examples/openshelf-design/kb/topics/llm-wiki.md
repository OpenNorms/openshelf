---
uid: 01a19d2e-d96b-7c70-b7c4-3429c27d93d5
title: LLM Wiki pattern
type: concept
summary: An LLM incrementally compiles raw sources into a persistent, interlinked Markdown wiki that it keeps current.
sources:
  - url: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
    retrieved: 2026-10-31
updated: 2026-10-31
---

Described by Andrej Karpathy as an alternative to retrieving from raw documents at query time. The LLM reads each new source once and folds it into the wiki: it writes a summary, updates entity and concept pages, and records contradictions. The wiki becomes "a persistent, compounding artifact".

There are three layers: immutable raw sources, the LLM-written wiki, and a schema file (such as `AGENTS.md` or `CLAUDE.md`) that the human and LLM refine together. The operations are ingest, query and lint, supported by an `index.md` catalog and an append-only `log.md`.

The gist leaves layout and formats open, which is what [[decisions/manifest-declares-layout]] preserves. OpenShelf adds [[progressive-context]] so that many such wikis can be connected to one project.
