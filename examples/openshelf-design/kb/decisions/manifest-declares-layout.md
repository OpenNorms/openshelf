---
uid: 01a19d2e-d96b-7e52-8f8e-33f0c6026100
title: The manifest declares the layout
type: decision
summary: KBs can be organized freely because consumers find everything through paths declared in kb.yaml.
updated: 2026-10-31
---

**Context.** People organize LLM wikis in very different ways, and the [[llm-wiki]] gist intentionally doesn't prescribe a structure. But connecting several KBs to one project needs tools and agents to find each KB's description, index and pages without guessing.

**Options considered.**
1. Fix one directory layout for every KB. Simple for tools, but forces existing wikis to be restructured.
2. Let each KB declare its layout in `kb.yaml`, with defaults. Tools read paths from the manifest.
3. Require no structure and rely on search. Flexible, but there's no reliable L1 and no stable page ids.

**Choice.** Option 2. `kb.yaml` is the only fixed path. Page ids come from paths under `layout.pages`, and links can be Markdown or wikilinks.

**Consequences.** Existing wikis, including Obsidian vaults, can become OpenShelf KBs by adding a manifest and summaries. Tools must read the manifest before anything else. This KB is itself organized differently from the default to show it works ([[progressive-context]] explains why the tiers still line up).
