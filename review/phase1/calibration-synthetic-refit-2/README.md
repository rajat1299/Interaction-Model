# Adjudicated refit 2 evidence heads

The 417 materialized browser bundles, runtime databases, and intermediate provenance records were removed after Phase 1 close because they are seed-deterministic and regenerable from the retained manifest, source package, input profile, and producer commit.

`calibration-manifest.json` preserves the population membership, seeds, producer commit, and SHA-256 digest of every removed artifact. `report-quantitative.json` is the frozen measured result. `SHA256SUMS` binds only the retained files in this directory; the original full-population inventory remains reachable in Git history at commit `d3f99cf3057541ea16f9cf4e0b9001b2c358e95d` and is recorded in the Phase 1 implementation log.
