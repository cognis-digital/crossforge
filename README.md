# crossforge

**Composition rendering for platform engineering.** Expose a small, high-level
API (a "claim") to your developers and *render* it into the concrete Kubernetes
resources that satisfy it — all declarative, all standard-library Python.

Part of the **Cognis Neural Suite**.

---

## Why

Platform teams increasingly hand developers a simple, self-service API
("give me a medium postgres") instead of raw YAML. crossforge implements that
pattern as a dependency-free renderer: a **definition** declares the claim's
parameters, a **composition** maps them onto resource templates, and a **claim**
is the request. No control plane to install, runs in CI and air-gapped.

## The three documents

```yaml
# definition.yaml — the API you expose
spec:
  claimKind: Database
  parameters:
    engine: {enum: [postgres, mysql], required: true}
    size:   {enum: [small, medium, large], default: small}

# composition.yaml — how it becomes real
spec:
  transforms:
    sizeToCpu: {type: map, map: {small: 250m, medium: 500m, large: "2"}}
  resources:
    - base: {kind: StatefulSet, spec: {... cpu: ${size | sizeToCpu} ...}}

# claim.yaml — the developer's request
kind: Database
spec: {parameters: {engine: postgres, size: medium}}
```

## Commands

```bash
python -m crossforge render   --definition def.yaml --composition comp.yaml --claim claim.yaml
python -m crossforge params   --definition def.yaml --claim claim.yaml
python -m crossforge validate --definition def.yaml --composition comp.yaml
python -m crossforge mcp        # local MCP server (stdio JSON-RPC)
```

## What sets crossforge apart

- **Type-preserving substitution.** A whole-string `${storageGi}` stays an int;
  inline `name-${x}` interpolates — so rendered manifests are valid, not
  stringified.
- **Transform vocabulary.** `map`, `default`, and `format` cover the common
  parameter-to-resource mappings without code.
- **Composition linting.** `validate` catches placeholders that reference
  undeclared parameters or unknown transforms before you ship.
- **MCP-native** (`render` / `validate`) and an opt-in local-fleet AI hook
  (default OFF) that drafts a definition + composition from a description.

## Tests

```bash
python -m pytest -q     # or: python -m unittest discover -s tests
```

## License

Cognis Open Collaboration License (COCL) 1.0 — see [`LICENSE`](LICENSE).
© 2026 Cognis Digital LLC. Original Cognis work; no third-party code, names, or
branding.
