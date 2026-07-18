# Trace-resampled calibration population

The 417 materialized browser bundles, runtime databases, and per-stream materialization records were removed after Phase 1 close because they are seed-deterministic and regenerable from the retained manifest, source package, input profile, and producer commit.

`calibration-manifest.json` preserves the population membership, seeds, producer commit, and SHA-256 digest of every removed artifact. `SHA256SUMS` binds only the retained files in this directory. The measured result remains in `../calibration-trace-analysis.json` and the final verdict in `../README.md`.
