---
uid: 01a19d2e-d814-74ff-8d51-a2a7e4aa39ba
title: python-can
summary: Python library for sending and receiving CAN messages across many interfaces, including SocketCAN.
type: entity
category: Libraries
url: https://pypi.org/project/python-can/
status: active
last_checked: 2026-10-31
tags: [library, python]
related: [cantools, socketcan]
sources:
  - url: https://pypi.org/project/python-can/
    retrieved: 2026-10-31
updated: 2026-10-31
---

python-can gives Python code one API for CAN hardware. Each backend
(`interface=`) maps to a driver or OS facility; on Linux the usual choice is
[SocketCAN](socketcan.md).

It handles the transport only. To turn raw frames into named signals, pair it
with a database decoder such as [cantools](cantools.md).
