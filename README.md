# E-Commerce Returns & RMA Synthetic Dataset Generator

A deterministic, rule-driven synthetic data engineering pipeline modeling the end-to-end post-purchase **Return Merchandise Authorization (RMA)** lifecycle, append-only state audit trails, multi-format relational exports (CSV, JSON, SQL), and isolated ground-truth anomaly labels.

---

## 1. Repository Structure

- docs/DATA_DICTIONARY.md — Complete schema, ERD, cardinalities, lifecycle states & policy rules
- src/config.py — Deterministic ID formatters, catalog & category policy rules
- src/master_gen.py — Master entity generator (Customer, Order, OrderLine) + EventTracker
- src/returns_gen.py — Downstream RMA lifecycle engine & post-baseline anomaly injector
- src/validator.py — PK/FK integrity, arithmetic reconciliation, date & audit checks
- src/exporter.py — Multi-format CSV/JSON/SQL exporter & SHA-256 manifest builder
- output/csv/ — 11 normalized input tables in CSV format
- output/json/ — 11 normalized input tables in JSON format
- output/sql/seed_data.sql — Relational DDL + batched INSERT statements
- output/ground_truth/ — Isolated anomaly labels (never leaked into input features)
- output/manifest.json & validation_summary.json — Seed metadata, SHA-256 checksums & QA audit report
- generate.py — Parameterized CLI entry point

---

## 2. Dataset Summary & Row Counts (--scale full, Seed 20261022)

All entities follow strict immutable zero-padded nomenclature (ORD-2026-000001, RMA-2026-000001, RMAL-<rma-id>-01, RTS-2026-000001, REF-2026-000001).

| Table / Entity | Primary Key | Row Count | Role & Lifecycle Coverage |
| :--- | :--- | ---: | :--- |
| customers | customer_id | 12,000 | Loyalty tiers (STANDARD-VIP), account dates & risk scores |
| orders | order_id | 30,000 | DELIVERED, SHIPPED, PLACED, CANCELLED with exact totals |
| order_lines | order_line_id | 65,210 | Multi-category line items, discounts, tax rates & return windows |
| return_requests | rma_id | 5,000 | Partial/full returns, exchanges, store credits, late requests & overrides |
| return_lines | return_line_id | 8,000 | Bridge mapping ReturnRequest to OrderLine with policy decisions |
| return_authorizations | auth_id | 4,271 | Issued RMAs (ISSUED, USED, EXPIRED) & warehouse routing |
| return_shipments | shipment_id | 4,271 | Carrier tracking including DELIVERED_TO_WAREHOUSE & missing shipments |
| inspections | inspection_id | 5,594 | Physical QA condition grading (PASS, PASS_WITH_FEE, FAIL_*) |
| refunds | refund_id | 3,810 | Reconciled item, tax, and restocking fee payouts |
| inventory_dispositions | disposition_id | 5,594 | Post-inspection actions (RESTOCK, REFURBISH, QUARANTINE, SCRAP) |
| state_event_log | event_id | 134,761 | Append-only state transition audit history across all entities |
| ground_truth (isolated) | anomaly_id | 75 | Labelled negative scenarios stored separately in output/ground_truth/ |

---

## 3. Isolated Ground-Truth Anomaly Breakdown

Baseline records are generated strictly from documented business rules first, followed by deterministic injection of 75 labelled edge cases (15 per scenario) into output/ground_truth/ground_truth.csv and ground_truth.json:

| Anomaly Issue Type | Target Entity | Count | Expected System Control Action |
| :--- | :--- | ---: | :--- |
| RETURN_QTY_EXCEEDS_PURCHASED | RETURN_LINE | 15 | BLOCK_RETURN_LINE |
| REFUND_EXCEEDS_PAID | REFUND | 15 | BLOCK_OVER_REFUND |
| RESTOCK_BEFORE_INSPECTION | INVENTORY_DISPOSITION | 15 | REJECT_PREMATURE_RESTOCK |
| LATE_RETURN_NO_OVERRIDE | RETURN_REQUEST | 15 | REJECT_OUT_OF_WINDOW |
| DUPLICATE_REFUND | REFUND | 15 | BLOCK_DUPLICATE_PAYOUT |

---

## 4. Validation & Reproducibility Metrics

- Validation Status: PASSED (0 structural, referential, arithmetic, or unlabelled policy errors)
- Fixed RNG Seed: 20261022 (Python standard library random.Random — zero external dependencies)
- Full Dataset SHA-256: b8c533c506119ce3d2af39249b88de94296b58d17619983f3c3686256df1e7e4
- Exported Artifacts: 25 deterministic files tracked in output/manifest.json

---

## 5. Usage Examples

- Starter dataset (600 orders, 100 RMAs, 160 return lines):
  python generate.py --seed 20261022 --scale starter --verify-reproducibility

- Full benchmark dataset (30,000 orders, 5,000 RMAs, 8,000 return lines):
  python generate.py --seed 20261022 --scale full

- Custom scale dataset:
  python generate.py --seed 20261022 --orders 10000 --returns 1500 --return-lines 2400 --output-dir custom_output

---

## 6. Lawful Use & Provenance

All customer identities, product SKUs, order histories, return events, and financial amounts are 100% synthetically generated via algorithmic rules. No external proprietary datasets or real personally identifiable information (PII) were used.
