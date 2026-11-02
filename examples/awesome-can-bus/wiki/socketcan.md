---
uid: 01a19d2e-d814-7c5b-b297-fe2b6c4ed530
title: SocketCAN
summary: Linux kernel CAN stack that exposes CAN interfaces as network devices used through the socket API.
type: concept
tags: [linux, kernel]
related: [python-can]
sources:
  - url: https://docs.kernel.org/networking/can.html
    retrieved: 2026-10-31
updated: 2026-10-31
---

SocketCAN puts CAN controllers behind the standard Linux networking model:
interfaces show up as `can0`, `vcan0` and so on, are configured with `ip link`,
and are read and written through sockets. A virtual `vcan` interface is handy
for testing without hardware.

Libraries such as [python-can](python-can.md) use it as their Linux backend.
