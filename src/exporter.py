import csv
import hashlib
import json
import os


SQL_DDL = """-- E-Commerce Returns & RMA Synthetic Dataset Seed SQL
-- Generated deterministically with fixed seed

CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(32) PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(160) UNIQUE NOT NULL,
    loyalty_tier VARCHAR(20) NOT NULL,
    account_created_date DATE NOT NULL,
    return_risk_score DECIMAL(4,2) NOT NULL,
    is_active BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(32) PRIMARY KEY,
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    order_date TIMESTAMP NOT NULL,
    delivered_date TIMESTAMP NULL,
    currency VARCHAR(3) NOT NULL,
    order_subtotal DECIMAL(12,2) NOT NULL,
    order_discount_total DECIMAL(12,2) NOT NULL,
    order_tax_total DECIMAL(12,2) NOT NULL,
    order_grand_total DECIMAL(12,2) NOT NULL,
    order_status VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS order_lines (
    order_line_id VARCHAR(40) PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    sku VARCHAR(32) NOT NULL,
    product_name VARCHAR(160) NOT NULL,
    category VARCHAR(40) NOT NULL,
    quantity_ordered INTEGER NOT NULL,
    unit_list_price DECIMAL(10,2) NOT NULL,
    unit_discount DECIMAL(10,2) NOT NULL,
    tax_rate DECIMAL(6,4) NOT NULL,
    line_subtotal DECIMAL(12,2) NOT NULL,
    line_discount DECIMAL(12,2) NOT NULL,
    line_tax DECIMAL(12,2) NOT NULL,
    line_paid_total DECIMAL(12,2) NOT NULL,
    return_window_days INTEGER NOT NULL,
    is_returnable BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS return_requests (
    rma_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    request_date TIMESTAMP NOT NULL,
    days_since_delivery INTEGER NOT NULL,
    request_type VARCHAR(20) NOT NULL,
    policy_override_flag BOOLEAN NOT NULL,
    request_status VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS return_lines (
    return_line_id VARCHAR(40) PRIMARY KEY,
    rma_id VARCHAR(32) NOT NULL REFERENCES return_requests(rma_id),
    order_line_id VARCHAR(40) NOT NULL REFERENCES order_lines(order_line_id),
    requested_qty INTEGER NOT NULL,
    approved_qty INTEGER NOT NULL,
    return_reason VARCHAR(40) NOT NULL,
    line_status VARCHAR(30) NOT NULL,
    expected_refund_amount DECIMAL(12,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS return_authorizations (
    auth_id VARCHAR(32) PRIMARY KEY,
    rma_id VARCHAR(32) UNIQUE NOT NULL REFERENCES return_requests(rma_id),
    authorized_date TIMESTAMP NOT NULL,
    expiration_date TIMESTAMP NOT NULL,
    return_warehouse_code VARCHAR(20) NOT NULL,
    auth_status VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS return_shipments (
    shipment_id VARCHAR(32) PRIMARY KEY,
    rma_id VARCHAR(32) NOT NULL REFERENCES return_requests(rma_id),
    auth_id VARCHAR(32) NOT NULL REFERENCES return_authorizations(auth_id),
    carrier VARCHAR(20) NOT NULL,
    tracking_number VARCHAR(40) UNIQUE NOT NULL,
    shipped_date TIMESTAMP NULL,
    received_date TIMESTAMP NULL,
    shipment_status VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS inspections (
    inspection_id VARCHAR(32) PRIMARY KEY,
    shipment_id VARCHAR(32) NOT NULL REFERENCES return_shipments(shipment_id),
    return_line_id VARCHAR(40) UNIQUE NOT NULL REFERENCES return_lines(return_line_id),
    inspected_date TIMESTAMP NOT NULL,
    inspector_id VARCHAR(20) NOT NULL,
    condition_grade VARCHAR(40) NOT NULL,
    inspection_result VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS refunds (
    refund_id VARCHAR(32) PRIMARY KEY,
    rma_id VARCHAR(32) NOT NULL REFERENCES return_requests(rma_id),
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    refund_date TIMESTAMP NOT NULL,
    refund_method VARCHAR(30) NOT NULL,
    gross_items_refund DECIMAL(12,2) NOT NULL,
    tax_refunded DECIMAL(12,2) NOT NULL,
    restocking_fee_deducted DECIMAL(12,2) NOT NULL,
    net_refund_amount DECIMAL(12,2) NOT NULL,
    refund_status VARCHAR(30) NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_dispositions (
    disposition_id VARCHAR(32) PRIMARY KEY,
    inspection_id VARCHAR(32) NULL REFERENCES inspections(inspection_id),
    return_line_id VARCHAR(40) NOT NULL REFERENCES return_lines(return_line_id),
    disposition_date TIMESTAMP NOT NULL,
    disposition_action VARCHAR(20) NOT NULL,
    quantity_processed INTEGER NOT NULL,
    target_bin_location VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS state_event_log (
    event_id VARCHAR(32) PRIMARY KEY,
    entity_type VARCHAR(30) NOT NULL,
    entity_id VARCHAR(40) NOT NULL,
    from_state VARCHAR(40) NULL,
    to_state VARCHAR(40) NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    actor VARCHAR(40) NOT NULL
);
"""


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sql_literal(val) -> str:
    if val is None or val == "":
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"


def export_all(tables: dict, validation_report: dict, output_dir: str, seed: int, scale_name: str, command_used: str) -> dict:
    csv_dir = os.path.join(output_dir, "csv")
    json_dir = os.path.join(output_dir, "json")
    sql_dir = os.path.join(output_dir, "sql")
    gt_dir = os.path.join(output_dir, "ground_truth")

    for d in (csv_dir, json_dir, sql_dir, gt_dir):
        os.makedirs(d, exist_ok=True)

    input_table_names = [
        "customers",
        "orders",
        "order_lines",
        "return_requests",
        "return_lines",
        "return_authorizations",
        "return_shipments",
        "inspections",
        "refunds",
        "inventory_dispositions",
        "state_event_log",
    ]

    checksums = {}

    # 1. Export Input Tables (CSV + JSON)
    for tname in input_table_names:
        rows = tables[tname]
        csv_path = os.path.join(csv_dir, f"{tname}.csv")
        json_path = os.path.join(json_dir, f"{tname}.json")

        if rows:
            fieldnames = list(rows[0].keys())
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)

        checksums[f"csv/{tname}.csv"] = sha256_file(csv_path)
        checksums[f"json/{tname}.json"] = sha256_file(json_path)

    # 2. Export Ground Truth Separately (Never mixed into input features)
    gt_rows = tables["ground_truth"]
    gt_csv = os.path.join(gt_dir, "ground_truth.csv")
    gt_json = os.path.join(gt_dir, "ground_truth.json")

    if gt_rows:
        with open(gt_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(gt_rows[0].keys()))
            writer.writeheader()
            writer.writerows(gt_rows)

    with open(gt_json, "w", encoding="utf-8") as f:
        json.dump(gt_rows, f, indent=2)

    checksums["ground_truth/ground_truth.csv"] = sha256_file(gt_csv)
    checksums["ground_truth/ground_truth.json"] = sha256_file(gt_json)

    # 3. Export SQL Seed File
    sql_path = os.path.join(sql_dir, "seed_data.sql")
    with open(sql_path, "w", newline="\n", encoding="utf-8") as f:
        f.write(SQL_DDL + "\n")
        for tname in input_table_names:
            rows = tables[tname]
            if not rows:
                continue
            cols = list(rows[0].keys())
            col_list = ", ".join(cols)
            f.write(f"-- Table: {tname} ({len(rows)} rows)\n")
            batch_size = 500
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                values_block = ",\n".join(
                    "    (" + ", ".join(_sql_literal(r[c]) for c in cols) + ")"
                    for r in batch
                )
                f.write(f"INSERT INTO {tname} ({col_list}) VALUES\n{values_block};\n\n")

    checksums["sql/seed_data.sql"] = sha256_file(sql_path)

    # 4. Export Validation Summary & Source Manifest
    val_path = os.path.join(output_dir, "validation_summary.json")
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(validation_report, f, indent=2)

    manifest = {
        "dataset_name": "E-Commerce Returns & RMA Synthetic Dataset",
        "provenance": "100% rule-based deterministic synthetic data; no external copyrighted or personal datasets used.",
        "seed": seed,
        "scale": scale_name,
        "generator_command": command_used,
        "row_counts": validation_report["row_counts"],
        "sha256_checksums": checksums,
    }
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest
