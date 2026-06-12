# Demo 01 — Turn a high-level claim into concrete resources

Three files model the platform-engineering pattern:

- `definition.yaml` — declares a `Database` claim with `engine`, `size`,
  `storageGi` parameters (with enums + defaults)
- `composition.yaml` — maps those parameters onto a `StatefulSet` + `PVC`, using
  `map` transforms (size→cpu, engine→image)
- `claim.yaml` — a developer's request: a medium postgres with 50Gi

## Run it

```bash
# Render the claim into concrete Kubernetes resources.
python -m crossforge render --definition demos/01-basic/definition.yaml \
    --composition demos/01-basic/composition.yaml \
    --claim demos/01-basic/claim.yaml

# Show the resolved parameters (defaults + claim values).
python -m crossforge params --definition demos/01-basic/definition.yaml \
    --claim demos/01-basic/claim.yaml

# Lint the composition: every ${placeholder} must resolve.
python -m crossforge validate --definition demos/01-basic/definition.yaml \
    --composition demos/01-basic/composition.yaml
```

## What you should see

The medium-postgres claim renders to a `StatefulSet` using image
`localhost:5000/postgres:16` with `cpu: 500m` (via the `sizeToCpu` transform)
and a `PersistentVolumeClaim` requesting `50` (storageGi from the claim). Change
`size` to `large` and the CPU request becomes `2` — the developer never touches
the low-level YAML.
