"""Command-line interface for crossforge."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from crossforge import TOOL_NAME, TOOL_VERSION
from crossforge.core import (
    CrossforgeError,
    load,
    render,
    resolve_params,
    validate_composition,
)


def _emit(text: str, out: Optional[str]) -> None:
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text if text.endswith("\n") else text + "\n")
        print(f"wrote {out}", file=sys.stderr)
    else:
        print(text)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Composition rendering — expand a high-level claim into the "
                    "concrete Kubernetes resources that satisfy it.")
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    sub = p.add_subparsers(dest="command")

    r = sub.add_parser("render", help="Render a claim through a composition.")
    r.add_argument("--definition", required=True)
    r.add_argument("--composition", required=True)
    r.add_argument("--claim", required=True)
    r.add_argument("--out")

    v = sub.add_parser("validate", help="Lint a composition against a definition.")
    v.add_argument("--definition", required=True)
    v.add_argument("--composition", required=True)
    v.add_argument("--format", choices=("table", "json"), default="table")

    pa = sub.add_parser("params", help="Show resolved params for a claim.")
    pa.add_argument("--definition", required=True)
    pa.add_argument("--claim", required=True)

    ex = sub.add_parser("explain", help="Explain a render: params + transforms per resource.")
    ex.add_argument("--definition", required=True)
    ex.add_argument("--composition", required=True)
    ex.add_argument("--claim", required=True)

    ra = sub.add_parser("render-all", help="Render many claims through one composition.")
    ra.add_argument("--definition", required=True)
    ra.add_argument("--composition", required=True)
    ra.add_argument("--claim", action="append", required=True, dest="claims",
                    metavar="CLAIM", help="Claim file (repeatable).")
    ra.add_argument("--out")

    sub.add_parser("mcp", help="Run as an MCP server (stdio JSON-RPC).")
    return p


def _run_render(a) -> int:
    try:
        resources = render(load(a.definition), load(a.composition), load(a.claim))
    except (OSError, CrossforgeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    blocks = [json.dumps(r, indent=2) for r in resources]
    _emit("\n---\n".join(blocks), a.out)
    return 0


def _run_validate(a) -> int:
    try:
        res = validate_composition(load(a.definition), load(a.composition))
    except (OSError, CrossforgeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.format == "json":
        print(json.dumps(res, indent=2))
    else:
        print(f"crossforge validate")
        print("=" * 56)
        for p in res["problems"]:
            print(f"  ! {p}")
        print(f"  declared: {', '.join(res['declared_params'])}")
        print(f"  used    : {', '.join(res['used_params'])}")
        print("RESULT: " + ("PASS" if res["ok"] else "FAIL"))
    return 0 if res["ok"] else 1


def _run_params(a) -> int:
    try:
        params = resolve_params(load(a.definition), load(a.claim))
    except (OSError, CrossforgeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(params, indent=2))
    return 0


def _run_explain(a) -> int:
    from crossforge import explain
    try:
        res = explain(load(a.definition), load(a.composition), load(a.claim))
    except (OSError, CrossforgeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(res, indent=2))
    return 0


def _run_render_all(a) -> int:
    from crossforge import render_all
    try:
        claims = [load(c) for c in a.claims]
        out = render_all(load(a.definition), load(a.composition), claims)
    except (OSError, CrossforgeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(out, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {a.out}", file=sys.stderr)
    else:
        print(text)
    return 0


def _run_mcp() -> int:
    from crossforge.mcp_server import run_mcp_server
    run_mcp_server()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "render":
        return _run_render(args)
    if args.command == "validate":
        return _run_validate(args)
    if args.command == "params":
        return _run_params(args)
    if args.command == "explain":
        return _run_explain(args)
    if args.command == "render-all":
        return _run_render_all(args)
    if args.command == "mcp":
        return _run_mcp()
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
