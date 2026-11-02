"""The `openshelf` command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, project
from .init import init
from .kb import KBError
from .lint import lint
from .uid import mint_missing


def _lint(args: argparse.Namespace) -> int:
    failed = False
    for path in args.paths:
        issues = lint(path)
        errors = [i for i in issues if i.level == "error"]
        for issue in issues:
            print(f"{path}: {issue}")
        failed |= bool(errors) or (args.strict and bool(issues))
        if not issues:
            print(f"{path}: ok")
    return 1 if failed else 0


def _init(args: argparse.Namespace) -> int:
    root = Path(args.path)
    init(root, id=args.id or root.resolve().name, title=args.title or args.id or root.resolve().name,
         description=args.description, license=args.license, visibility=args.visibility)
    print(f"Created KB in {root}")
    return 0


def _uid(args: argparse.Namespace) -> int:
    try:
        result = mint_missing(args.path)
    except KBError as e:
        print(f"openshelf: {e}", file=sys.stderr)
        return 1
    print(f"KB uid: {result['kb']}; pages: {result['pages_minted']} minted, "
          f"{result['pages_existing']} already had one, {result['pages_skipped']} skipped (no usable frontmatter)")
    return 0


def _add(args: argparse.Namespace) -> int:
    root = project.find_root(args.project)
    entry = project.add(root, args.source, id=args.id, ref=args.ref, path=args.path, use=args.use)
    print(f"Added {entry['id']} to {root / project.DIR / project.KBS}")
    if not args.no_sync:
        return _sync(argparse.Namespace(project=str(root), offline=False, locked=False))
    return 0


def _sync(args: argparse.Namespace) -> int:
    root = project.find_root(args.project)
    kbs = project.sync(root, offline=args.offline, locked=args.locked)
    for kb in kbs:
        print(f"{kb.id}: {kb.root}")
    print(f"Wrote {root / project.DIR / project.CONTEXT}")
    return 0


def _mcp(args: argparse.Namespace) -> int:
    try:
        from .server import build_server
    except ImportError:
        print("openshelf: the MCP server needs the 'mcp' extra: pip install 'openshelf[mcp]'", file=sys.stderr)
        return 1
    build_server(project.find_root(args.project)).run("stdio")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openshelf", description="Tools for OpenShelf knowledge bases.")
    parser.add_argument("--version", action="version", version=f"openshelf {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create a new KB with the default layout")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--id", help="KB id (default: directory name)")
    p.add_argument("--title")
    p.add_argument("--description", required=True, help="one-line L0 description, at most 300 characters")
    p.add_argument("--license", default=None, help="SPDX id for the content (default: CC-BY-4.0, or none when --visibility private)")
    p.add_argument("--visibility", choices=["public", "internal", "private"], default=None,
                   help="who the KB may be shared with (default: public); non-public KBs stay out of committed project files")
    p.set_defaults(func=_init)

    p = sub.add_parser("lint", help="check KBs against the spec")
    p.add_argument("paths", nargs="*", default=["."])
    p.add_argument("--strict", action="store_true", help="fail on warnings too")
    p.set_defaults(func=_lint)

    p = sub.add_parser("uid", help="mint any missing KB and page uids (the §4.1 adoption path)")
    p.add_argument("path", nargs="?", default=".")
    p.set_defaults(func=_uid)

    p = sub.add_parser("add", help="connect a KB to this project")
    p.add_argument("source", help="github:owner/repo, a git URL, or a local path relative to the project root")
    p.add_argument("--id", help="KB id (default: read from the KB's kb.yaml)")
    p.add_argument("--ref", help="branch, tag or commit")
    p.add_argument("--path", help="subdirectory of the source that holds kb.yaml")
    p.add_argument("--use", help="when an agent should consult this KB")
    p.add_argument("--no-sync", action="store_true", help="don't run sync afterwards")
    p.add_argument("--project", default=".", help="project directory (default: nearest with .openshelf/kbs.yaml)")
    p.set_defaults(func=_add)

    p = sub.add_parser("sync", help="fetch connected KBs and regenerate .openshelf/context.md")
    p.add_argument("--offline", action="store_true", help="use the cache only")
    p.add_argument("--locked", action="store_true", help="check out the commits in .openshelf/kbs.lock")
    p.add_argument("--project", default=".")
    p.set_defaults(func=_sync)

    p = sub.add_parser("mcp", help="run an MCP server (stdio) exposing the connected KBs")
    p.add_argument("--project", default=".")
    p.set_defaults(func=_mcp)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (project.ProjectError, FileExistsError) as e:
        print(f"openshelf: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
