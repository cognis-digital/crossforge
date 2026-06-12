# crossforge — Usage Guide

crossforge expands a high-level *claim* into the concrete Kubernetes resources
that satisfy it, using a declarative *definition* (the parameter API) and a
*composition* (resource templates + transforms).

## The three documents

```yaml
# definition.yaml
spec:
  claimKind: Database
  parameters:
    engine: {enum: [postgres, mysql], required: true}
    size:   {enum: [small, medium, large], default: small}

# composition.yaml
spec:
  transforms:
    sizeToCpu: {type: map, map: {small: 250m, medium: 500m, large: "2"}}
  resources:
    - base: {kind: StatefulSet, spec: {... cpu: ${size | sizeToCpu} ...}}

# claim.yaml
kind: Database
spec: {parameters: {engine: postgres, size: medium}}
```

## Transforms

| type     | effect                                              |
|----------|-----------------------------------------------------|
| `map`    | look up the value in `map` (else `default`)         |
| `default`| substitute `value` when empty/None                  |
| `format` | `fmt` with `{}` replaced by the value               |
| `prefix` | prepend `value`                                     |
| `suffix` | append `value`                                      |
| `int`    | coerce to int (else `default`)                      |
| `upper` / `lower` | case-fold                                  |

Transforms chain left-to-right: `${name | prefix | upper}`.

## Commands

```bash
# Render one claim.
python -m crossforge render --definition def.yaml --composition comp.yaml --claim claim.yaml

# Resolve parameters (defaults + claim values).
python -m crossforge params --definition def.yaml --claim claim.yaml

# Explain a render: resolved params + the placeholders each resource uses.
python -m crossforge explain --definition def.yaml --composition comp.yaml --claim claim.yaml

# Render a fleet of claims through one composition.
python -m crossforge render-all --definition def.yaml --composition comp.yaml \
    --claim orders.yaml --claim billing.yaml --out all.json

# Lint: every ${placeholder} must resolve to a declared param/transform.
python -m crossforge validate --definition def.yaml --composition comp.yaml

# MCP server (render / validate).
python -m crossforge mcp
```

## Type-preserving substitution

A whole-string placeholder keeps its type — `storage: ${storageGi}` renders the
integer `50`, not the string `"50"`. Inline placeholders interpolate as strings:
`name: ${app}-db` → `name: orders-db`. This keeps rendered manifests valid.

## render-all for fleets

`render-all` is the multi-tenant pattern: one composition, many claims (one
`Database` per team), each rendered independently into its own resource set,
keyed by claim name.
