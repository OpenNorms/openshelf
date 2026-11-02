---
uid: 01a19d2e-d96c-79a7-a8f4-1d13f51a34e8
title: Progressive context
type: concept
summary: Load knowledge in tiers, from a one-line description down to raw sources, only as deep as a task needs.
updated: 2026-10-31
---

An agent connected to many KBs can't read all of them. OpenShelf gives every KB the same four tiers:

1. **L0:** the one-line `description` from `kb.yaml`, always in context.
2. **L1:** the index, read when a task touches the KB's area.
3. **L2:** individual pages, opened when relevant.
4. **L3:** raw sources, consulted only to verify or extend a page.

Because L0 is short and the tiers are the same everywhere, adding a KB to a project costs a few lines of context until it's actually needed. This only works if consumers can find each tier in any KB, which is why the layout is declared in the manifest ([[manifest-declares-layout]]).
