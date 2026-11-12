import random
from datetime import timedelta
from src.config import (
    BASE_START_DATE,
    CATEGORY_POLICIES,
    FIRST_NAMES,
    LAST_NAMES,
    PRODUCT_CATALOG,
    TAX_RATES,
    fmt_customer_id,
    fmt_event_id,
    fmt_order_id,
    fmt_order_line_id,
    iso_ts,
)


class EventTracker:
    """Append-only state transition logger."""

    def __init__(self):
        self.events = []
        self._seq = 1

    def log(self, entity_type: str, entity_id: str, from_state, to_state: str, timestamp: str, actor: str):
        self.events.append({
            "event_id": fmt_event_id(self._seq),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "from_state": from_state if from_state is not None else "",
            "to_state": to_state,
            "event_timestamp": timestamp,
            "actor": actor,
        })
        self._seq += 1


def generate_master_data(rng: random.Random, num_orders: int, event_tracker: EventTracker):
    num_customers = max(100, int(num_orders * 0.40))
    customers = []
    customer_created_dt = {}

    loyalty_choices = ["STANDARD", "SILVER", "GOLD", "VIP"]
    loyalty_weights = [0.55, 0.25, 0.14, 0.06]

    for c_seq in range(1, num_customers + 1):
        cid = fmt_customer_id(c_seq)
        fname = rng.choice(FIRST_NAMES)
        lname = rng.choice(LAST_NAMES)
        created_dt = BASE_START_DATE + timedelta(
            days=rng.randint(0, 90),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
        customer_created_dt[cid] = created_dt
        risk_score = round(min(1.0, max(0.0, rng.betavariate(1.5, 6.5))), 2)

        customers.append({
            "customer_id": cid,
            "full_name": f"{fname} {lname}",
            "email": f"{fname.lower()}.{lname.lower()}.{c_seq}@example.test",
            "loyalty_tier": rng.choices(loyalty_choices, weights=loyalty_weights, k=1)[0],
            "account_created_date": created_dt.strftime("%Y-%m-%d"),
            "return_risk_score": f"{risk_score:.2f}",
            "is_active": rng.random() > 0.02,
        })

    orders = []
    order_lines = []

    status_choices = ["DELIVERED", "SHIPPED", "PLACED", "CANCELLED"]
    status_weights = [0.88, 0.05, 0.03, 0.04]

    for o_seq in range(1, num_orders + 1):
        oid = fmt_order_id(o_seq)
        cust = customers[rng.randint(0, num_customers - 1)]
        cid = cust["customer_id"]
        c_created = customer_created_dt[cid]

        order_dt = c_created + timedelta(
            days=rng.randint(0, 180),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
            seconds=rng.randint(0, 59),
        )
        order_status = rng.choices(status_choices, weights=status_weights, k=1)[0]
        tax_rate = rng.choice(TAX_RATES)
        tier_discount_max = {"STANDARD": 0.10, "SILVER": 0.15, "GOLD": 0.20, "VIP": 0.25}[cust["loyalty_tier"]]

        num_lines = rng.choices([1, 2, 3, 4, 5], weights=[0.35, 0.32, 0.18, 0.10, 0.05], k=1)[0]
        chosen_products = rng.sample(PRODUCT_CATALOG, k=num_lines)

        subtotal_acc = 0.0
        discount_acc = 0.0
        tax_acc = 0.0

        for line_idx, (sku, prod_name, category, base_price) in enumerate(chosen_products, start=1):
            olid = fmt_order_line_id(oid, line_idx)
            qty = rng.choices([1, 2, 3, 4], weights=[0.65, 0.22, 0.09, 0.04], k=1)[0]

            if rng.random() < 0.45:
                disc_pct = round(rng.uniform(0.05, tier_discount_max), 2)
                unit_discount = round(base_price * disc_pct, 2)
            else:
                unit_discount = 0.00

            line_subtotal = round(base_price * qty, 2)
            line_discount = round(unit_discount * qty, 2)
            line_net = round(line_subtotal - line_discount, 2)
            line_tax = round(line_net * tax_rate, 2)
            line_paid_total = round(line_net + line_tax, 2)

            policy = CATEGORY_POLICIES[category]

            order_lines.append({
                "order_line_id": olid,
                "order_id": oid,
                "sku": sku,
                "product_name": prod_name,
                "category": category,
                "quantity_ordered": qty,
                "unit_list_price": f"{base_price:.2f}",
                "unit_discount": f"{unit_discount:.2f}",
                "tax_rate": f"{tax_rate:.4f}",
                "line_subtotal": f"{line_subtotal:.2f}",
                "line_discount": f"{line_discount:.2f}",
                "line_tax": f"{line_tax:.2f}",
                "line_paid_total": f"{line_paid_total:.2f}",
                "return_window_days": policy["return_window_days"],
                "is_returnable": policy["is_returnable"],
            })

            subtotal_acc = round(subtotal_acc + line_subtotal, 2)
            discount_acc = round(discount_acc + line_discount, 2)
            tax_acc = round(tax_acc + line_tax, 2)

        grand_total = round(subtotal_acc - discount_acc + tax_acc, 2)

        event_tracker.log("ORDER", oid, None, "PLACED", iso_ts(order_dt), "CUSTOMER")
        delivered_str = ""

        if order_status == "CANCELLED":
            cancel_dt = order_dt + timedelta(hours=rng.randint(1, 24))
            event_tracker.log("ORDER", oid, "PLACED", "CANCELLED", iso_ts(cancel_dt), "CUSTOMER")
        elif order_status in ("SHIPPED", "DELIVERED"):
            ship_dt = order_dt + timedelta(days=rng.randint(1, 3), hours=rng.randint(1, 12))
            event_tracker.log("ORDER", oid, "PLACED", "SHIPPED", iso_ts(ship_dt), "SYSTEM_POLICY_ENGINE")
            if order_status == "DELIVERED":
                deliv_dt = ship_dt + timedelta(days=rng.randint(2, 7), hours=rng.randint(1, 18))
                delivered_str = iso_ts(deliv_dt)
                event_tracker.log("ORDER", oid, "SHIPPED", "DELIVERED", delivered_str, "CARRIER_WEBHOOK")

        orders.append({
            "order_id": oid,
            "customer_id": cid,
            "order_date": iso_ts(order_dt),
            "delivered_date": delivered_str,
            "currency": "USD",
            "order_subtotal": f"{subtotal_acc:.2f}",
            "order_discount_total": f"{discount_acc:.2f}",
            "order_tax_total": f"{tax_acc:.2f}",
            "order_grand_total": f"{grand_total:.2f}",
            "order_status": order_status,
        })

    return customers, orders, order_lines
