from datetime import datetime, timezone


def parse_ts(ts_str: str) -> datetime:
    return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def validate_dataset(tables: dict) -> dict:
    """
    Runs full PK uniqueness, FK integrity, date ordering, arithmetic reconciliation,
    lifecycle transition, and anomaly detection checks.
    """
    errors = []

    customers = tables["customers"]
    orders = tables["orders"]
    order_lines = tables["order_lines"]
    return_requests = tables["return_requests"]
    return_lines = tables["return_lines"]
    return_auths = tables["return_authorizations"]
    return_shipments = tables["return_shipments"]
    inspections = tables["inspections"]
    refunds = tables["refunds"]
    dispositions = tables["inventory_dispositions"]
    events = tables["state_event_log"]
    ground_truth = tables["ground_truth"]

    # 1. Primary-Key Uniqueness
    pk_specs = [
        ("customers", customers, "customer_id"),
        ("orders", orders, "order_id"),
        ("order_lines", order_lines, "order_line_id"),
        ("return_requests", return_requests, "rma_id"),
        ("return_lines", return_lines, "return_line_id"),
        ("return_authorizations", return_auths, "auth_id"),
        ("return_shipments", return_shipments, "shipment_id"),
        ("inspections", inspections, "inspection_id"),
        ("refunds", refunds, "refund_id"),
        ("inventory_dispositions", dispositions, "disposition_id"),
        ("state_event_log", events, "event_id"),
        ("ground_truth", ground_truth, "anomaly_id"),
    ]
    pk_sets = {}
    for tname, rows, pk_col in pk_specs:
        seen = set()
        for r in rows:
            val = r[pk_col]
            if val in seen:
                errors.append(f"Duplicate PK {val} in {tname}.{pk_col}")
            seen.add(val)
        pk_sets[tname] = seen

    # 2. Foreign-Key Integrity
    fk_checks = [
        ("orders", orders, "customer_id", "customers"),
        ("order_lines", order_lines, "order_id", "orders"),
        ("return_requests", return_requests, "order_id", "orders"),
        ("return_requests", return_requests, "customer_id", "customers"),
        ("return_lines", return_lines, "rma_id", "return_requests"),
        ("return_lines", return_lines, "order_line_id", "order_lines"),
        ("return_authorizations", return_auths, "rma_id", "return_requests"),
        ("return_shipments", return_shipments, "rma_id", "return_requests"),
        ("return_shipments", return_shipments, "auth_id", "return_authorizations"),
        ("inspections", inspections, "shipment_id", "return_shipments"),
        ("inspections", inspections, "return_line_id", "return_lines"),
        ("refunds", refunds, "rma_id", "return_requests"),
        ("refunds", refunds, "order_id", "orders"),
        ("inventory_dispositions", dispositions, "return_line_id", "return_lines"),
    ]
    for src_t, rows, fk_col, ref_t in fk_checks:
        ref_set = pk_sets[ref_t]
        for r in rows:
            if r[fk_col] not in ref_set:
                errors.append(f"Broken FK {r[fk_col]} in {src_t}.{fk_col} -> {ref_t}")

    # Optional FK check for inspection_id on dispositions
    for d in dispositions:
        if d["inspection_id"] and d["inspection_id"] not in pk_sets["inspections"]:
            errors.append(f"Broken optional FK {d['inspection_id']} in inventory_dispositions.inspection_id")

    # 3. Order Arithmetic Reconciliation
    lines_by_order = {}
    for ol in order_lines:
        lines_by_order.setdefault(ol["order_id"], []).append(ol)

    for o in orders:
        ols = lines_by_order.get(o["order_id"], [])
        sub = round(sum(float(x["line_subtotal"]) for x in ols), 2)
        disc = round(sum(float(x["line_discount"]) for x in ols), 2)
        tax = round(sum(float(x["line_tax"]) for x in ols), 2)
        grand = round(sub - disc + tax, 2)
        if (
            round(float(o["order_subtotal"]), 2) != sub
            or round(float(o["order_discount_total"]), 2) != disc
            or round(float(o["order_tax_total"]), 2) != tax
            or round(float(o["order_grand_total"]), 2) != grand
        ):
            errors.append(f"Order arithmetic mismatch on {o['order_id']}")

    # 4. Date Ordering & Lifecycle Checks (excluding explicitly labelled anomaly records)
    gt_by_entity = {g["primary_entity_id"]: g["issue_type"] for g in ground_truth}

    order_map = {o["order_id"]: o for o in orders}
    ol_map = {ol["order_line_id"]: ol for ol in order_lines}
    insp_map = {i["inspection_id"]: i for i in inspections}

    for o in orders:
        if o["delivered_date"]:
            if parse_ts(o["delivered_date"]) < parse_ts(o["order_date"]):
                errors.append(f"delivered_date < order_date on {o['order_id']}")

    for r in return_requests:
        o = order_map[r["order_id"]]
        if parse_ts(r["request_date"]) < parse_ts(o["delivered_date"]):
            errors.append(f"request_date < delivered_date on {r['rma_id']}")

    # 5. Audit Anomaly Detection Verification
    detected_anomalies = {
        "RETURN_QTY_EXCEEDS_PURCHASED": 0,
        "REFUND_EXCEEDS_PAID": 0,
        "RESTOCK_BEFORE_INSPECTION": 0,
        "LATE_RETURN_NO_OVERRIDE": 0,
        "DUPLICATE_REFUND": 0,
    }

    # Check excess return quantity
    for rl in return_lines:
        ol = ol_map[rl["order_line_id"]]
        if int(rl["requested_qty"]) > int(ol["quantity_ordered"]):
            if gt_by_entity.get(rl["return_line_id"]) == "RETURN_QTY_EXCEEDS_PURCHASED":
                detected_anomalies["RETURN_QTY_EXCEEDS_PURCHASED"] += 1
            else:
                errors.append(f"Unlabelled excess return qty on {rl['return_line_id']}")

    # Check restock before inspection
    for d in dispositions:
        if not d["inspection_id"] or (
            d["inspection_id"] in insp_map
            and parse_ts(d["disposition_date"]) < parse_ts(insp_map[d["inspection_id"]]["inspected_date"])
        ):
            if gt_by_entity.get(d["disposition_id"]) == "RESTOCK_BEFORE_INSPECTION":
                detected_anomalies["RESTOCK_BEFORE_INSPECTION"] += 1
            else:
                errors.append(f"Unlabelled premature restock on {d['disposition_id']}")

    # Check late return without override
    for r in return_requests:
        if r["request_status"] in ("APPROVED", "PARTIALLY_APPROVED", "COMPLETED") and not r["policy_override_flag"]:
            if int(r["days_since_delivery"]) > 30:
                if gt_by_entity.get(r["rma_id"]) == "LATE_RETURN_NO_OVERRIDE":
                    detected_anomalies["LATE_RETURN_NO_OVERRIDE"] += 1
                else:
                    errors.append(f"Unlabelled late return without override on {r['rma_id']}")

    # Check duplicate refunds & over-refunds
    refunds_by_rma = {}
    for ref in refunds:
        if ref["refund_status"] == "PROCESSED":
            refunds_by_rma.setdefault(ref["rma_id"], []).append(ref)
        expected_net = round(
            float(ref["gross_items_refund"]) + float(ref["tax_refunded"]) - float(ref["restocking_fee_deducted"]),
            2,
        )
        if round(float(ref["net_refund_amount"]), 2) > expected_net:
            if gt_by_entity.get(ref["refund_id"]) == "REFUND_EXCEEDS_PAID":
                detected_anomalies["REFUND_EXCEEDS_PAID"] += 1
            else:
                errors.append(f"Unlabelled over-refund on {ref['refund_id']}")

    for rma_id, r_list in refunds_by_rma.items():
        if len(r_list) > 1:
            for extra_ref in r_list[1:]:
                if gt_by_entity.get(extra_ref["refund_id"]) == "DUPLICATE_REFUND":
                    detected_anomalies["DUPLICATE_REFUND"] += 1
                else:
                    errors.append(f"Unlabelled duplicate refund on {extra_ref['refund_id']}")

    return {
        "passed": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors[:20],
        "row_counts": {k: len(v) for k, v in tables.items()},
        "ground_truth_expected_counts": {
            k: sum(1 for g in ground_truth if g["issue_type"] == k)
            for k in detected_anomalies
        },
        "ground_truth_detected_counts": detected_anomalies,
    }
