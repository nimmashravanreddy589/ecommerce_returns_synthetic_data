import random
from datetime import datetime, timedelta, timezone
from src.config import (
    CATEGORY_POLICIES,
    fmt_anomaly_id,
    fmt_auth_id,
    fmt_disposition_id,
    fmt_inspection_id,
    fmt_refund_id,
    fmt_return_line_id,
    fmt_rma_id,
    fmt_shipment_id,
    iso_ts,
)


def parse_ts(ts_str: str) -> datetime:
    return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def generate_returns_lifecycle(
    rng: random.Random,
    orders: list,
    order_lines: list,
    num_returns: int,
    num_return_lines: int,
    event_tracker,
):
    """
    Builds ReturnRequest, ReturnLine, ReturnAuthorization, ReturnShipment,
    Inspection, Refund, InventoryDisposition, and GroundTruthAnomaly records.
    """
    # Index delivered orders and their lines
    lines_by_order = {}
    for ol in order_lines:
        lines_by_order.setdefault(ol["order_id"], []).append(ol)

    delivered_orders = [o for o in orders if o["order_status"] == "DELIVERED" and o["order_id"] in lines_by_order]
    if not delivered_orders:
        raise ValueError("No delivered orders available to generate returns.")

    # Track remaining returnable quantity per order_line_id so multiple RMAs never accidentally exceed purchased qty in baseline
    remaining_qty = {ol["order_line_id"]: int(ol["quantity_ordered"]) for ol in order_lines}

    # Determine how many lines each of the num_returns requests will have so total equals num_return_lines
    if num_return_lines < num_returns:
        raise ValueError("num_return_lines must be >= num_returns")

    line_counts = [1] * num_returns
    extra_lines_needed = num_return_lines - num_returns
    # Distribute extra lines across RMAs (up to 4 lines per RMA)
    candidate_indices = list(range(num_returns))
    while extra_lines_needed > 0:
        idx = rng.choice(candidate_indices)
        if line_counts[idx] < 4:
            line_counts[idx] += 1
            extra_lines_needed -= 1

    return_requests = []
    return_lines = []
    return_auths = []
    return_shipments = []
    inspections = []
    refunds = []
    dispositions = []
    ground_truth = []

    auth_seq = 1
    ship_seq = 1
    insp_seq = 1
    ref_seq = 1
    disp_seq = 1
    anom_seq = 1

    request_types = ["REFUND", "EXCHANGE", "STORE_CREDIT"]
    request_type_weights = [0.74, 0.16, 0.10]

    reasons = [
        "SIZE_FIT",
        "DEFECTIVE",
        "DAMAGED_IN_TRANSIT",
        "CHANGED_MIND",
        "WRONG_ITEM_SENT",
        "NOT_AS_DESCRIBED",
    ]
    reason_weights = [0.30, 0.18, 0.12, 0.22, 0.08, 0.10]

    carriers = ["UPS", "FEDEX", "USPS", "DHL"]
    warehouses = ["WH-EAST-01", "WH-WEST-02", "WH-CENTRAL-03"]

    # Track clean candidate records for deliberate post-baseline anomaly injection
    clean_eligible_rmas = []

    for r_idx in range(num_returns):
        rma_seq = r_idx + 1
        rma_id = fmt_rma_id(rma_seq)
        target_lines = line_counts[r_idx]

        # Pick an order that has enough lines with remaining returnable qty
        order = None
        available_ols = []
        for _ in range(40):
            cand = rng.choice(delivered_orders)
            avail = [ol for ol in lines_by_order[cand["order_id"]] if remaining_qty[ol["order_line_id"]] > 0]
            if len(avail) >= target_lines:
                order = cand
                available_ols = avail
                break
        if order is None:
            # Fallback: pick any delivered order with at least 1 remaining line
            for cand in delivered_orders:
                avail = [ol for ol in lines_by_order[cand["order_id"]] if remaining_qty[ol["order_line_id"]] > 0]
                if avail:
                    order = cand
                    available_ols = avail
                    target_lines = min(target_lines, len(avail))
                    break

        chosen_ols = rng.sample(available_ols, k=target_lines)
        deliv_dt = parse_ts(order["delivered_date"])

        # 84% within normal window (1-13 days), 10% between 16-28 days, 6% clearly late (35-65 days)
        timing_roll = rng.random()
        if timing_roll < 0.84:
            days_after = rng.randint(1, 13)
        elif timing_roll < 0.94:
            days_after = rng.randint(16, 28)
        else:
            days_after = rng.randint(35, 65)

        req_dt = deliv_dt + timedelta(days=days_after, hours=rng.randint(1, 20), minutes=rng.randint(0, 59))
        days_since_delivery = (req_dt.date() - deliv_dt.date()).days

        req_type = rng.choices(request_types, weights=request_type_weights, k=1)[0]
        # VIP/Gold or occasional customer service exception grants policy override on late returns
        policy_override = (days_since_delivery > 14) and (rng.random() < 0.25)

        event_tracker.log("RETURN_REQUEST", rma_id, None, "SUBMITTED", iso_ts(req_dt), "CUSTOMER")

        rma_line_objs = []
        approved_count = 0
        rejected_count = 0

        for l_idx, ol in enumerate(chosen_ols, start=1):
            rmal_id = fmt_return_line_id(rma_id, l_idx)
            olid = ol["order_line_id"]
            max_q = remaining_qty[olid]
            # Partial quantity returns when ordered > 1
            req_qty = 1 if max_q == 1 else rng.randint(1, max_q)
            remaining_qty[olid] -= req_qty

            reason = rng.choices(reasons, weights=reason_weights, k=1)[0]
            is_returnable = bool(ol["is_returnable"])
            window_days = int(ol["return_window_days"])

            # Policy evaluation
            if not is_returnable:
                line_status = "REJECTED_NON_RETURNABLE"
                app_qty = 0
                rejected_count += 1
            elif days_since_delivery > window_days and not policy_override:
                line_status = "REJECTED_POLICY_WINDOW"
                app_qty = 0
                rejected_count += 1
            else:
                line_status = "APPROVED"
                app_qty = req_qty
                approved_count += 1

            # Calculate expected refund math for approved quantity
            unit_price = float(ol["unit_list_price"])
            unit_disc = float(ol["unit_discount"])
            tax_rate = float(ol["tax_rate"])
            fee_rate = CATEGORY_POLICIES[ol["category"]]["restocking_fee_rate"]

            # Waive restocking fee for merchant fault / defect
            if reason in ("DEFECTIVE", "WRONG_ITEM_SENT", "DAMAGED_IN_TRANSIT"):
                fee_rate = 0.0

            net_paid_items = round((unit_price - unit_disc) * app_qty, 2)
            tax_ref = round(net_paid_items * tax_rate, 2)
            restock_fee = round(net_paid_items * fee_rate, 2)
            expected_refund = round(net_paid_items + tax_ref - restock_fee, 2) if app_qty > 0 else 0.00

            rl_record = {
                "return_line_id": rmal_id,
                "rma_id": rma_id,
                "order_line_id": olid,
                "requested_qty": req_qty,
                "approved_qty": app_qty,
                "return_reason": reason,
                "line_status": line_status,
                "expected_refund_amount": f"{expected_refund:.2f}",
                # Internal helper fields stripped before CSV export
                "_net_paid_items": net_paid_items,
                "_tax_ref": tax_ref,
                "_restock_fee": restock_fee,
                "_category": ol["category"],
                "_unit_net_paid": round(unit_price - unit_disc, 2),
                "_tax_rate": tax_rate,
            }
            return_lines.append(rl_record)
            rma_line_objs.append(rl_record)

        if approved_count == 0:
            req_status = "REJECTED"
        elif rejected_count > 0:
            req_status = "PARTIALLY_APPROVED"
        else:
            req_status = "APPROVED"

        eval_dt = req_dt + timedelta(minutes=rng.randint(5, 120))
        actor = "MANUAL_OVERRIDE_AGENT" if policy_override else "SYSTEM_POLICY_ENGINE"
        event_tracker.log("RETURN_REQUEST", rma_id, "SUBMITTED", req_status, iso_ts(eval_dt), actor)

        rma_record = {
            "rma_id": rma_id,
            "order_id": order["order_id"],
            "customer_id": order["customer_id"],
            "request_date": iso_ts(req_dt),
            "days_since_delivery": days_since_delivery,
            "request_type": req_type,
            "policy_override_flag": policy_override,
            "request_status": req_status,
        }
        return_requests.append(rma_record)

        # If rejected completely, no authorization/shipment/refund occurs
        if req_status == "REJECTED":
            continue

        # 1. ReturnAuthorization
        auth_id = fmt_auth_id(auth_seq)
        auth_seq += 1
        auth_dt = eval_dt + timedelta(minutes=rng.randint(1, 15))
        exp_dt = auth_dt + timedelta(days=14)
        wh_code = rng.choice(warehouses)
        event_tracker.log("RETURN_AUTH", auth_id, None, "ISSUED", iso_ts(auth_dt), "SYSTEM_POLICY_ENGINE")

        # 2. ReturnShipment (8% never shipped, 3% lost in transit, 89% delivered to warehouse)
        ship_id = fmt_shipment_id(ship_seq)
        ship_seq += 1
        carrier = rng.choice(carriers)
        tracking = f"1Z{rma_seq:06d}{ship_seq:08d}"
        ship_roll = rng.random()

        if ship_roll < 0.08:
            # Missing shipment (customer never dropped off)
            ship_status = "LABEL_CREATED_NOT_SHIPPED"
            auth_status = "EXPIRED"
            event_tracker.log("RETURN_SHIPMENT", ship_id, None, ship_status, iso_ts(auth_dt), "SYSTEM_POLICY_ENGINE")
            event_tracker.log("RETURN_AUTH", auth_id, "ISSUED", "EXPIRED", iso_ts(exp_dt), "SYSTEM_POLICY_ENGINE")
            return_auths.append({
                "auth_id": auth_id,
                "rma_id": rma_id,
                "authorized_date": iso_ts(auth_dt),
                "expiration_date": iso_ts(exp_dt),
                "return_warehouse_code": wh_code,
                "auth_status": auth_status,
            })
            return_shipments.append({
                "shipment_id": ship_id,
                "rma_id": rma_id,
                "auth_id": auth_id,
                "carrier": carrier,
                "tracking_number": tracking,
                "shipped_date": "",
                "received_date": "",
                "shipment_status": ship_status,
            })
            continue

        shipped_dt = auth_dt + timedelta(days=rng.randint(1, 6), hours=rng.randint(1, 18))
        event_tracker.log("RETURN_AUTH", auth_id, "ISSUED", "USED", iso_ts(shipped_dt), "CARRIER_WEBHOOK")
        event_tracker.log("RETURN_SHIPMENT", ship_id, None, "IN_TRANSIT", iso_ts(shipped_dt), "CARRIER_WEBHOOK")

        if ship_roll < 0.11:
            ship_status = "LOST_IN_TRANSIT"
            event_tracker.log("RETURN_SHIPMENT", ship_id, "IN_TRANSIT", ship_status, iso_ts(shipped_dt + timedelta(days=7)), "CARRIER_WEBHOOK")
            return_auths.append({
                "auth_id": auth_id,
                "rma_id": rma_id,
                "authorized_date": iso_ts(auth_dt),
                "expiration_date": iso_ts(exp_dt),
                "return_warehouse_code": wh_code,
                "auth_status": "USED",
            })
            return_shipments.append({
                "shipment_id": ship_id,
                "rma_id": rma_id,
                "auth_id": auth_id,
                "carrier": carrier,
                "tracking_number": tracking,
                "shipped_date": iso_ts(shipped_dt),
                "received_date": "",
                "shipment_status": ship_status,
            })
            continue

        received_dt = shipped_dt + timedelta(days=rng.randint(2, 6), hours=rng.randint(1, 14))
        ship_status = "DELIVERED_TO_WAREHOUSE"
        event_tracker.log("RETURN_SHIPMENT", ship_id, "IN_TRANSIT", ship_status, iso_ts(received_dt), "CARRIER_WEBHOOK")

        return_auths.append({
            "auth_id": auth_id,
            "rma_id": rma_id,
            "authorized_date": iso_ts(auth_dt),
            "expiration_date": iso_ts(exp_dt),
            "return_warehouse_code": wh_code,
            "auth_status": "USED",
        })
        return_shipments.append({
            "shipment_id": ship_id,
            "rma_id": rma_id,
            "auth_id": auth_id,
            "carrier": carrier,
            "tracking_number": tracking,
            "shipped_date": iso_ts(shipped_dt),
            "received_date": iso_ts(received_dt),
            "shipment_status": ship_status,
        })

        # 3. Inspection & InventoryDisposition for each APPROVED ReturnLine
        approved_lines = [rl for rl in rma_line_objs if rl["line_status"] == "APPROVED"]
        latest_insp_dt = received_dt

        gross_ref_acc = 0.0
        tax_ref_acc = 0.0
        fee_ref_acc = 0.0
        rma_inspections = []
        rma_dispositions = []

        for rl in approved_lines:
            insp_id = fmt_inspection_id(insp_seq)
            insp_seq += 1
            insp_dt = received_dt + timedelta(hours=rng.randint(2, 36), minutes=rng.randint(0, 59))
            if insp_dt > latest_insp_dt:
                latest_insp_dt = insp_dt

            cat = rl["_category"]
            reason = rl["return_reason"]

            if reason in ("DEFECTIVE", "DAMAGED_IN_TRANSIT"):
                cond = rng.choice(["DEFECTIVE_UNREPAIRABLE", "HEAVILY_DAMAGED", "MINOR_COSMETIC_DAMAGE"])
            elif cat == "BEAUTY_PERSONAL_CARE":
                cond = rng.choices(["NEW_UNOPENED", "HYGIENE_SEAL_BROKEN"], weights=[0.82, 0.18], k=1)[0]
            elif cat == "ELECTRONICS":
                cond = rng.choices(["NEW_UNOPENED", "OPEN_BOX_ELECTRONICS", "MINOR_COSMETIC_DAMAGE"], weights=[0.45, 0.45, 0.10], k=1)[0]
            else:
                cond = rng.choices(["NEW_UNOPENED", "LIKE_NEW", "MINOR_COSMETIC_DAMAGE", "HEAVILY_DAMAGED"], weights=[0.50, 0.35, 0.10, 0.05], k=1)[0]

            # Map condition_grade -> inspection_result & disposition_action
            if cond in ("NEW_UNOPENED", "LIKE_NEW"):
                insp_res = "PASS"
                disp_action = "RESTOCK"
                bin_prefix = "BIN-RS"
            elif cond in ("OPEN_BOX_ELECTRONICS", "MINOR_COSMETIC_DAMAGE"):
                insp_res = "PASS_WITH_FEE" if rl["_restock_fee"] > 0 else "PASS"
                disp_action = "REFURBISH"
                bin_prefix = "BIN-RF"
            elif cond == "HYGIENE_SEAL_BROKEN":
                insp_res = "FAIL_SEAL_BROKEN"
                disp_action = "QUARANTINE"
                bin_prefix = "BIN-QR"
            else:
                insp_res = "FAIL_DAMAGED"
                disp_action = "SCRAP"
                bin_prefix = "BIN-SC"

            inspector = f"EMP-{rng.randint(1001, 1085)}"
            event_tracker.log("INSPECTION", insp_id, None, insp_res, iso_ts(insp_dt), "QA_INSPECTOR")

            insp_rec = {
                "inspection_id": insp_id,
                "shipment_id": ship_id,
                "return_line_id": rl["return_line_id"],
                "inspected_date": iso_ts(insp_dt),
                "inspector_id": inspector,
                "condition_grade": cond,
                "inspection_result": insp_res,
            }
            inspections.append(insp_rec)
            rma_inspections.append(insp_rec)

            # 4. InventoryDisposition (always post-inspection in clean baseline)
            disp_id = fmt_disposition_id(disp_seq)
            disp_seq += 1
            disp_dt = insp_dt + timedelta(minutes=rng.randint(10, 180))
            event_tracker.log("DISPOSITION", disp_id, None, disp_action, iso_ts(disp_dt), "QA_INSPECTOR")

            disp_rec = {
                "disposition_id": disp_id,
                "inspection_id": insp_id,
                "return_line_id": rl["return_line_id"],
                "disposition_date": iso_ts(disp_dt),
                "disposition_action": disp_action,
                "quantity_processed": rl["approved_qty"],
                "target_bin_location": f"{bin_prefix}-{rng.randint(100, 999)}",
            }
            dispositions.append(disp_rec)
            rma_dispositions.append(disp_rec)

            # Accumulate refund for passed lines (or merchant-damaged lines)
            if insp_res in ("PASS", "PASS_WITH_FEE") or reason in ("DEFECTIVE", "DAMAGED_IN_TRANSIT", "WRONG_ITEM_SENT"):
                gross_ref_acc = round(gross_ref_acc + rl["_net_paid_items"], 2)
                tax_ref_acc = round(tax_ref_acc + rl["_tax_ref"], 2)
                fee_ref_acc = round(fee_ref_acc + rl["_restock_fee"], 2)

        net_refund = round(gross_ref_acc + tax_ref_acc - fee_ref_acc, 2)
        ref_id = fmt_refund_id(ref_seq)
        ref_seq += 1
        ref_dt = latest_insp_dt + timedelta(hours=rng.randint(1, 24))

        ref_method = {
            "REFUND": "ORIGINAL_PAYMENT",
            "STORE_CREDIT": "STORE_CREDIT",
            "EXCHANGE": "EXCHANGE_CREDIT",
        }[req_type]

        ref_status = "PROCESSED" if net_refund > 0 else "FAILED"
        event_tracker.log("REFUND", ref_id, None, "PENDING", iso_ts(latest_insp_dt + timedelta(minutes=15)), "SYSTEM_POLICY_ENGINE")
        event_tracker.log("REFUND", ref_id, "PENDING", ref_status, iso_ts(ref_dt), "FINANCE_BATCH")
        event_tracker.log("RETURN_REQUEST", rma_id, req_status, "COMPLETED", iso_ts(ref_dt), "SYSTEM_POLICY_ENGINE")
        rma_record["request_status"] = "COMPLETED"

        ref_rec = {
            "refund_id": ref_id,
            "rma_id": rma_id,
            "order_id": order["order_id"],
            "refund_date": iso_ts(ref_dt),
            "refund_method": ref_method,
            "gross_items_refund": f"{gross_ref_acc:.2f}",
            "tax_refunded": f"{tax_ref_acc:.2f}",
            "restocking_fee_deducted": f"{fee_ref_acc:.2f}",
            "net_refund_amount": f"{net_refund:.2f}",
            "refund_status": ref_status,
        }
        refunds.append(ref_rec)

        if ref_status == "PROCESSED" and len(approved_lines) >= 1 and len(rma_inspections) >= 1:
            clean_eligible_rmas.append({
                "rma": rma_record,
                "order": order,
                "approved_lines": approved_lines,
                "inspections": rma_inspections,
                "dispositions": rma_dispositions,
                "refund": ref_rec,
            })

    # =========================================================================
    # STEP 5: INJECT LABELLED EDGE CASES / NEGATIVE ANOMALIES (~1.5% of RMAs)
    # =========================================================================
    ol_lookup = {ol["order_line_id"]: ol for ol in order_lines}
    num_per_type = max(1, int(num_returns * 0.003))  # e.g., 15 per type (75 total) at 5,000 RMAs

    # Shuffle clean candidates deterministically and reserve disjoint sets for each anomaly type
    rng.shuffle(clean_eligible_rmas)
    needed_total = num_per_type * 5
    selected = clean_eligible_rmas[:needed_total]

    # 1. RETURN_QTY_EXCEEDS_PURCHASED
    for item in selected[0:num_per_type]:
        rl = item["approved_lines"][0]
        ol = ol_lookup[rl["order_line_id"]]
        purchased = int(ol["quantity_ordered"])
        rl["requested_qty"] = purchased + 2
        rl["approved_qty"] = purchased + 2
        ground_truth.append({
            "anomaly_id": fmt_anomaly_id(anom_seq),
            "issue_type": "RETURN_QTY_EXCEEDS_PURCHASED",
            "primary_entity_type": "RETURN_LINE",
            "primary_entity_id": rl["return_line_id"],
            "rma_id": item["rma"]["rma_id"],
            "order_id": item["order"]["order_id"],
            "expected_rule_violated": f"requested_qty ({purchased + 2}) exceeds OrderLine.quantity_ordered ({purchased})",
            "expected_system_action": "BLOCK_RETURN_LINE",
        })
        anom_seq += 1

    # 2. REFUND_EXCEEDS_PAID
    for item in selected[num_per_type : 2 * num_per_type]:
        ref = item["refund"]
        orig_net = float(ref["net_refund_amount"])
        inflated = round(orig_net + 75.00, 2)
        ref["net_refund_amount"] = f"{inflated:.2f}"
        ground_truth.append({
            "anomaly_id": fmt_anomaly_id(anom_seq),
            "issue_type": "REFUND_EXCEEDS_PAID",
            "primary_entity_type": "REFUND",
            "primary_entity_id": ref["refund_id"],
            "rma_id": item["rma"]["rma_id"],
            "order_id": item["order"]["order_id"],
            "expected_rule_violated": f"net_refund_amount ({inflated:.2f}) exceeds reconciled paid total ({orig_net:.2f})",
            "expected_system_action": "BLOCK_OVER_REFUND",
        })
        anom_seq += 1

    # 3. RESTOCK_BEFORE_INSPECTION
    for item in selected[2 * num_per_type : 3 * num_per_type]:
        disp = item["dispositions"][0]
        insp = item["inspections"][0]
        insp_dt = parse_ts(insp["inspected_date"])
        premature_dt = insp_dt - timedelta(hours=12)
        disp["disposition_action"] = "RESTOCK"
        disp["disposition_date"] = iso_ts(premature_dt)
        disp["inspection_id"] = ""
        ground_truth.append({
            "anomaly_id": fmt_anomaly_id(anom_seq),
            "issue_type": "RESTOCK_BEFORE_INSPECTION",
            "primary_entity_type": "INVENTORY_DISPOSITION",
            "primary_entity_id": disp["disposition_id"],
            "rma_id": item["rma"]["rma_id"],
            "order_id": item["order"]["order_id"],
            "expected_rule_violated": f"disposition_date ({iso_ts(premature_dt)}) precedes inspection ({insp['inspected_date']}) with null inspection_id",
            "expected_system_action": "REJECT_PREMATURE_RESTOCK",
        })
        anom_seq += 1

    # 4. LATE_RETURN_NO_OVERRIDE
    for item in selected[3 * num_per_type : 4 * num_per_type]:
        rma = item["rma"]
        deliv_dt = parse_ts(item["order"]["delivered_date"])
        late_req_dt = deliv_dt + timedelta(days=52)
        rma["request_date"] = iso_ts(late_req_dt)
        rma["days_since_delivery"] = 52
        rma["policy_override_flag"] = False
        ground_truth.append({
            "anomaly_id": fmt_anomaly_id(anom_seq),
            "issue_type": "LATE_RETURN_NO_OVERRIDE",
            "primary_entity_type": "RETURN_REQUEST",
            "primary_entity_id": rma["rma_id"],
            "rma_id": rma["rma_id"],
            "order_id": item["order"]["order_id"],
            "expected_rule_violated": "Approved return submitted 52 days after delivery (> max 30-day window) with policy_override_flag=False",
            "expected_system_action": "REJECT_OUT_OF_WINDOW",
        })
        anom_seq += 1

    # 5. DUPLICATE_REFUND
    for item in selected[4 * num_per_type : 5 * num_per_type]:
        orig_ref = item["refund"]
        dup_ref_id = fmt_refund_id(ref_seq)
        ref_seq += 1
        dup_dt = parse_ts(orig_ref["refund_date"]) + timedelta(minutes=18)
        dup_ref = {
            "refund_id": dup_ref_id,
            "rma_id": orig_ref["rma_id"],
            "order_id": orig_ref["order_id"],
            "refund_date": iso_ts(dup_dt),
            "refund_method": orig_ref["refund_method"],
            "gross_items_refund": orig_ref["gross_items_refund"],
            "tax_refunded": orig_ref["tax_refunded"],
            "restocking_fee_deducted": orig_ref["restocking_fee_deducted"],
            "net_refund_amount": orig_ref["net_refund_amount"],
            "refund_status": "PROCESSED",
        }
        refunds.append(dup_ref)
        event_tracker.log("REFUND", dup_ref_id, None, "PROCESSED", iso_ts(dup_dt), "FINANCE_BATCH")
        ground_truth.append({
            "anomaly_id": fmt_anomaly_id(anom_seq),
            "issue_type": "DUPLICATE_REFUND",
            "primary_entity_type": "REFUND",
            "primary_entity_id": dup_ref_id,
            "rma_id": orig_ref["rma_id"],
            "order_id": orig_ref["order_id"],
            "expected_rule_violated": f"Duplicate PROCESSED refund ({dup_ref_id}) issued for RMA already refunded via {orig_ref['refund_id']}",
            "expected_system_action": "BLOCK_DUPLICATE_PAYOUT",
        })
        anom_seq += 1

    # Strip internal helper keys from return_lines before returning
    clean_return_lines = [
        {k: v for k, v in rl.items() if not k.startswith("_")}
        for rl in return_lines
    ]

    return {
        "return_requests": return_requests,
        "return_lines": clean_return_lines,
        "return_authorizations": return_auths,
        "return_shipments": return_shipments,
        "inspections": inspections,
        "refunds": refunds,
        "inventory_dispositions": dispositions,
        "ground_truth": ground_truth,
    }
