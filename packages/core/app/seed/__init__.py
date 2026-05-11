"""Seed loaders for built-in catalogs and reference PoCs.

- `tech_catalog.yaml` + `seeder.seed_tech_catalog()` ship the 13 dimensions /
  76 items panorama (SPEC section 13.2).
- `reference/<slug>/` + `seeder.seed_reference_pocs()` ship the three
  scrubbed reference projects (SPEC section 13.1). Lands in Step 0.8.

The seeder functions are idempotent: re-running them inserts only missing
rows. They are invoked from `workshop db seed` (CLI) and from tests that
need pre-populated data.
"""
