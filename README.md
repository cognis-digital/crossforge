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

## Interoperability

`crossforge` composes with the 300+ tool Cognis suite — JSON in/out and a shared
OpenAI-compatible `/v1` backbone. See **[INTEROP.md](INTEROP.md)** for the
suite map, composition patterns, and reference stacks.

## Integrations

Forward `crossforge`'s findings to STIX/MISP/Sigma/Splunk/Elastic/Slack/webhooks via
[`cognis-connect`](https://github.com/cognis-digital/cognis-connect). See **[INTEGRATIONS.md](INTEGRATIONS.md)**.

## License

Cognis Open Collaboration License (COCL) 1.0 — see [`LICENSE`](LICENSE).
© 2026 Cognis Digital LLC. Original Cognis work; no third-party code, names, or
branding.

<!-- cognis:domains:start -->
## Domains

**Primary domain:** AI & ML  ·  **JTF MERIDIAN division:** ATHENA-PRIME · SAGE

**Topics:** `cognis` `ai` `llm` `machine-learning` `kubernetes`

Part of the **Cognis Neural Suite** — 300+ source-available tools organized across 12 domains under the JTF MERIDIAN command structure. See the [suite on GitHub](https://github.com/cognis-digital) and [jtf-meridian](https://github.com/cognis-digital/jtf-meridian) for how the pieces fit together.
<!-- cognis:domains:end -->

## Usage — step by step

`crossforge` renders a high-level **claim** through a **composition** into the concrete Kubernetes resources that satisfy it — three documents, no control plane.

1. **Install** (pure stdlib, Python 3.10+):
   ```bash
   pip install "git+https://github.com/cognis-digital/crossforge.git"
   ```
2. **Validate** that your composition matches the definition's parameters before rendering (exits non-zero on problems):
   ```bash
   crossforge validate --definition def.yaml --composition comp.yaml
   ```
3. **Inspect resolved params** for a claim (defaults + overrides applied):
   ```bash
   crossforge params --definition def.yaml --claim claim.yaml
   ```
4. **Render** the claim into resources (write with `--out`), or `explain` to see the params + transforms applied per resource:
   ```bash
   crossforge render  --definition def.yaml --composition comp.yaml --claim claim.yaml --out out.yaml
   crossforge explain --definition def.yaml --composition comp.yaml --claim claim.yaml
   ```
5. **Automate** — render many claims through one composition in CI:
   ```bash
   crossforge render-all --definition def.yaml --composition comp.yaml --claim a.yaml --claim b.yaml --out rendered.yaml
   ```
   Or run it as a local MCP server (stdio JSON-RPC): `crossforge mcp`.
