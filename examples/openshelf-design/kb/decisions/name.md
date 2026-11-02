---
uid: 01a19d2e-d96b-7fd0-9ebe-8946c2c497c3
title: The name OpenShelf
type: decision
summary: Renamed from OpenKB to OpenShelf to avoid a popular project of the same name, using a shelf metaphor for connected KBs.
sources:
  - url: https://github.com/VectifyAI/OpenKB
    retrieved: 2026-10-31
  - url: https://pypi.org/project/openkb/
    retrieved: 2026-10-31
updated: 2026-10-31
---

**Context.** The project started as OpenKB. VectifyAI's OpenKB, an LLM-maintained wiki tool built on the same [[llm-wiki]] pattern, already used that name, owned `openkb` on PyPI, and had a few thousand GitHub stars. Sharing the name would have meant confusion and no package name.

**Options considered.** Keep OpenKB and publish as `openkb-cli`; library words such as tome, sheaf and carrel (all taken by tools in this space); kbshelf; kbdock; OpenShelf.

**Choice.** OpenShelf. It keeps the "Open" from OpenKB and says what the project adds: many KBs on one project's shelf. The shelf also explains [[progressive-context]]: spine (L0), table of contents (L1), pages (L2), references (L3).

**Consequences.** The command, package and project folder are `openshelf` and `.openshelf/`; the manifest stays `kb.yaml`. The flagship KB, awesome-kb, is a separate name for a separate thing. An unrelated Android book-library app also called Openshelf exists, but it is in a different field.
