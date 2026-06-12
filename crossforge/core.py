"""Core engine for crossforge — composition rendering.

crossforge expands a high-level *claim* (a small request like "I want a postgres
database, size medium") into the concrete set of Kubernetes resources that
satisfy it, using a declarative *composition* that maps claim parameters onto
templated resources.

The model has three pieces, all declarative YAML/JSON:

  * definition  — declares a claim kind and its parameter schema (names +
                  defaults + required)
  * composition — a list of resource templates with ``${param}`` placeholders
                  and a small transform vocabulary (default/map/format)
  * claim       — the user's request: kind + parameter values

``render`` validates the claim against the definition, applies defaults and
transforms, and emits the concrete resources. This is the platform-engineering
"expose a high-level API, render the low-level reality" pattern as a
dependency-free CLI.

This is original Cognis Digital work; it shares no code, names, or branding with
any other control-plane framework.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

TOOL_NAME = "crossforge"
TOOL_VERSION = "0.1.0"

_PLACEHOLDER = re.compile(r"\$\{([^}]+)\}")


class CrossforgeError(Exception):
    """User-facing composition/claim error."""


# --------------------------------------------------------------------------- #
# YAML subset (mappings/lists/scalars/inline lists)
# --------------------------------------------------------------------------- #

def _coerce(text: str) -> Any:
    s = text.strip()
    if s in ("", "~", "null"):
        return None
    if s in ("true", "false"):
        return s == "true"
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
        inner = s[1:-1].strip()
        return [] if not inner else [_coerce(p) for p in inner.split(",")]
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def parse_yaml_subset(text: str) -> Any:
    lines = text.replace("\t", "  ").splitlines()
    toks: List[Tuple[int, str]] = []
    for raw in lines:
        out, sgl, dbl = [], False, False
        for i, ch in enumerate(raw):
            if ch == "'" and not dbl:
                sgl = not sgl
            elif ch == '"' and not sgl:
                dbl = not dbl
            elif ch == "#" and not sgl and not dbl and (i == 0 or raw[i-1] in " \t"):
                break
            out.append(ch)
        line = "".join(out).rstrip()
        if not line.strip() or line.strip() == "---":
            continue
        indent = len(line) - len(line.lstrip(" "))
        toks.append((indent, line.strip()))
    if not toks:
        return {}
    pos = [0]

    def kv(s):
        i = s.find(":")
        if i == -1:
            return s, ""
        k, v = s[:i].strip(), s[i+1:].strip()
        if len(k) >= 2 and k[0] == k[-1] and k[0] in "\"'":
            k = k[1:-1]
        return k, v

    def parse_block(indent):
        if pos[0] >= len(toks):
            return None
        _c, content = toks[pos[0]]
        return parse_list(indent) if content.startswith("- ") else parse_map(indent)

    def parse_list(indent):
        items = []
        while pos[0] < len(toks):
            cur, content = toks[pos[0]]
            if cur != indent or not content.startswith("- "):
                break
            inner = content[2:].strip()
            pos[0] += 1
            if ":" in inner and not (inner.find(":")+1 < len(inner)
                                     and inner[inner.find(":")+1] != " "):
                k, v = kv(inner)
                obj = {k: (_coerce(v) if v else _child(indent + 2))}
                obj.update(cont_map(indent + 2))
                items.append(obj)
            elif inner == "":
                items.append(_child(indent + 2))
            else:
                items.append(_coerce(inner))
        return items

    def cont_map(indent):
        obj = {}
        while pos[0] < len(toks):
            cur, content = toks[pos[0]]
            if cur != indent or content.startswith("- "):
                break
            k, v = kv(content)
            pos[0] += 1
            obj[k] = _coerce(v) if v else _child(indent + 2)
        return obj

    def parse_map(indent):
        obj = {}
        while pos[0] < len(toks):
            cur, content = toks[pos[0]]
            if cur != indent or content.startswith("- "):
                break
            k, v = kv(content)
            pos[0] += 1
            obj[k] = _coerce(v) if v else _child(indent + 1)
        return obj

    def _child(min_indent):
        if pos[0] >= len(toks):
            return None
        cur, content = toks[pos[0]]
        if cur < min_indent:
            return None
        return parse_list(cur) if content.startswith("- ") else parse_map(cur)

    result = parse_block(0)
    return result if result is not None else {}


def load(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise CrossforgeError(f"file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    ext = os.path.splitext(path)[1].lower()
    try:
        data = json.loads(text) if ext == ".json" else parse_yaml_subset(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise CrossforgeError(f"could not parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CrossforgeError("document root must be a mapping")
    return data


# --------------------------------------------------------------------------- #
# Parameter resolution
# --------------------------------------------------------------------------- #

def resolve_params(definition: Dict[str, Any],
                   claim: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a claim against a definition; apply defaults; return params."""
    spec = definition.get("spec", definition)
    declared = spec.get("parameters", {}) or {}
    claim_params = (claim.get("spec", {}) or {}).get("parameters", {}) or {}

    resolved: Dict[str, Any] = {}
    for name, meta in declared.items():
        meta = meta or {}
        if name in claim_params:
            resolved[name] = claim_params[name]
        elif "default" in meta:
            resolved[name] = meta["default"]
        elif meta.get("required"):
            raise CrossforgeError(f"required parameter missing: {name}")
        else:
            resolved[name] = None
        # enum validation
        if meta.get("enum") and resolved[name] not in meta["enum"]:
            raise CrossforgeError(
                f"parameter {name}={resolved[name]!r} not in {meta['enum']}")
    # Unknown params are a hard error (catch typos).
    for name in claim_params:
        if name not in declared:
            raise CrossforgeError(f"unknown parameter in claim: {name}")
    # Always expose the claim name.
    resolved["__name__"] = (claim.get("metadata", {}) or {}).get("name", "claim")
    return resolved


# --------------------------------------------------------------------------- #
# Transforms + placeholder substitution
# --------------------------------------------------------------------------- #

def _apply_transform(value: Any, transform: Dict[str, Any]) -> Any:
    kind = transform.get("type")
    if kind == "map":
        mapping = transform.get("map", {})
        return mapping.get(str(value), transform.get("default", value))
    if kind == "default":
        return transform.get("value") if value in (None, "") else value
    if kind == "format":
        return str(transform.get("fmt", "{}")).replace("{}", str(value))
    if kind == "prefix":
        return f"{transform.get('value', '')}{value}"
    if kind == "suffix":
        return f"{value}{transform.get('value', '')}"
    if kind == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return transform.get("default", 0)
    if kind == "upper":
        return str(value).upper()
    if kind == "lower":
        return str(value).lower()
    return value


def _resolve_token(token: str, params: Dict[str, Any]) -> Any:
    """Resolve ``param`` or ``param | transform_name`` against params/transforms."""
    name = token.strip()
    if name in params:
        return params[name]
    # dotted path into a param value
    head = name.split(".")[0]
    if head in params and isinstance(params[head], dict):
        cur: Any = params[head]
        for part in name.split(".")[1:]:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur
    return None


def _substitute(node: Any, params: Dict[str, Any],
                transforms: Dict[str, Dict[str, Any]]) -> Any:
    if isinstance(node, dict):
        return {k: _substitute(v, params, transforms) for k, v in node.items()}
    if isinstance(node, list):
        return [_substitute(v, params, transforms) for v in node]
    if isinstance(node, str):
        # Whole-string placeholder => preserve type; inline => string interpolate.
        m = _PLACEHOLDER.fullmatch(node.strip())
        if m:
            return _eval_placeholder(m.group(1), params, transforms)

        def repl(mm):
            val = _eval_placeholder(mm.group(1), params, transforms)
            return "" if val is None else str(val)
        return _PLACEHOLDER.sub(repl, node)
    return node


def _eval_placeholder(expr: str, params: Dict[str, Any],
                      transforms: Dict[str, Dict[str, Any]]) -> Any:
    parts = [p.strip() for p in expr.split("|")]
    value = _resolve_token(parts[0], params)
    for tname in parts[1:]:
        if tname in transforms:
            value = _apply_transform(value, transforms[tname])
    return value


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #

def render(definition: Dict[str, Any], composition: Dict[str, Any],
           claim: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Render a claim into concrete resources via the composition."""
    params = resolve_params(definition, claim)
    comp_spec = composition.get("spec", composition)
    transforms = comp_spec.get("transforms", {}) or {}
    resources = comp_spec.get("resources", []) or []
    if not resources:
        raise CrossforgeError("composition has no resources")

    out: List[Dict[str, Any]] = []
    for entry in resources:
        base = entry.get("base", entry)
        rendered = _substitute(base, params, transforms)
        out.append(rendered)
    return out


def render_all(definition: Dict[str, Any], composition: Dict[str, Any],
               claims: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Render many claims through one composition.

    Returns {claim_name: [resources]}. A failing claim raises; use this for a
    fleet of same-kind claims (e.g. one Database per team).
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    for claim in claims:
        name = (claim.get("metadata", {}) or {}).get("name", f"claim-{len(out)}")
        out[name] = render(definition, composition, claim)
    return out


def explain(definition: Dict[str, Any], composition: Dict[str, Any],
            claim: Dict[str, Any]) -> Dict[str, Any]:
    """Explain a render: resolved params + which transforms each placeholder uses."""
    params = resolve_params(definition, claim)
    comp_spec = composition.get("spec", composition)
    usage: List[Dict[str, Any]] = []
    for entry in comp_spec.get("resources", []) or []:
        base = entry.get("base", entry)
        kind = base.get("kind", "?")
        refs: List[str] = []

        def scan(node):
            if isinstance(node, dict):
                for v in node.values():
                    scan(v)
            elif isinstance(node, list):
                for v in node:
                    scan(v)
            elif isinstance(node, str):
                for m in _PLACEHOLDER.finditer(node):
                    refs.append(m.group(1).strip())
        scan(base)
        usage.append({"kind": kind, "placeholders": sorted(set(refs))})
    return {"params": {k: v for k, v in params.items() if k != "__name__"},
            "claim_name": params.get("__name__"),
            "resources": usage}


def validate_composition(definition: Dict[str, Any],
                         composition: Dict[str, Any]) -> Dict[str, Any]:
    """Lint: every placeholder used must resolve to a declared param or transform."""
    spec = definition.get("spec", definition)
    # __name__ (the claim's metadata.name) is always injected by resolve_params.
    declared = set((spec.get("parameters", {}) or {}).keys()) | {"__name__"}
    comp_spec = composition.get("spec", composition)
    transforms = set((comp_spec.get("transforms", {}) or {}).keys())

    problems: List[str] = []
    used: set = set()

    def scan(node):
        if isinstance(node, dict):
            for v in node.values():
                scan(v)
        elif isinstance(node, list):
            for v in node:
                scan(v)
        elif isinstance(node, str):
            for m in _PLACEHOLDER.finditer(node):
                parts = [p.strip() for p in m.group(1).split("|")]
                used.add(parts[0].split(".")[0])
                for t in parts[1:]:
                    if t not in transforms:
                        problems.append(f"unknown transform: {t}")

    for entry in comp_spec.get("resources", []) or []:
        scan(entry.get("base", entry))

    for p in used:
        if p not in declared:
            problems.append(f"placeholder references undeclared parameter: {p}")

    return {"ok": not problems, "problems": sorted(set(problems)),
            "declared_params": sorted(declared), "used_params": sorted(used)}


# --------------------------------------------------------------------------- #
# AI hook (opt-in, default OFF)
# --------------------------------------------------------------------------- #

def draft_composition(description: str) -> Dict[str, Any]:
    out = {"definition": {}, "composition": {},
           "_ai": "disabled — set COGNIS_AI_BACKEND to enable"}
    backend = _load_ai_backend()
    if backend is None or not backend.is_enabled() or not backend.health():
        return out
    prompt = ("Output ONLY JSON with keys 'definition' (claim parameter schema) "
              "and 'composition' (resource templates with ${param} placeholders) "
              "for this platform abstraction. No prose.\n\n"
              f"ABSTRACTION:\n{description}\n")
    try:
        content = backend._chat("Return strict JSON only.", prompt)
    except Exception:
        return out
    parsed = _extract_json_object(content or "")
    if isinstance(parsed, dict) and "composition" in parsed:
        parsed["_ai"] = "drafted by local fleet"
        return parsed
    return out


def _load_ai_backend():
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.abspath(os.path.join(here, "..", "..", "..", "_shared",
                                        "cognis_ai_backend.py"))
    if os.path.isfile(cand):
        try:
            spec = importlib.util.spec_from_file_location("cognis_ai_backend", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            return mod.CognisAIBackend()
        except Exception:
            return None
    return None


def _extract_json_object(text: str) -> Any:
    text = (text or "").strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
