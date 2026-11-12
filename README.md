# E-Commerce Returns & RMA Synthetic Dataset Generator

Deterministic, rule-driven synthetic data pipeline modeling the post-purchase E-Commerce Return Merchandise Authorization (RMA) lifecycle, append-only state audit logs, and isolated ground-truth anomaly evaluation labels.

## Commands
- Starter scale: `python generate.py --seed 20261022 --scale starter --verify-reproducibility`
- Full scale: `python generate.py --seed 20261022 --scale full --verify-reproducibility`

## Schema & Provenance
- Full Data Dictionary & Cardinality: `docs/DATA_DICTIONARY.md`
- Exports: `output/csv/`, `output/json/`, `output/sql/seed_data.sql`, and isolated `output/ground_truth/`
- Lawful Use: 100% synthetic data generated with fixed seed `20261022` using Python standard libraries.
