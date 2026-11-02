---
uid: 01a19d2e-d813-7999-8572-a8850f14f67c
title: cantools
summary: Python package to parse CAN databases (such as DBC files) and encode or decode messages and signals.
type: entity
category: Libraries
url: https://pypi.org/project/cantools/
status: active
last_checked: 2026-10-31
tags: [library, python, dbc]
related: [python-can]
sources:
  - url: https://pypi.org/project/cantools/
    retrieved: 2026-10-31
updated: 2026-10-31
---

cantools loads a CAN database and converts between raw frame bytes and
physical signal values. It doesn't talk to hardware itself; it is commonly
used with [python-can](python-can.md) to read frames from a bus and decode
them.
