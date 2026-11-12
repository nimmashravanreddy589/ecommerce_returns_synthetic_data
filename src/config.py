from datetime import datetime, timezone

YEAR_PREFIX = "2026"
BASE_START_DATE = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)

CATEGORY_POLICIES = {
    "APPAREL": {
        "return_window_days": 30,
        "is_returnable": True,
        "restocking_fee_rate": 0.00,
    },
    "ELECTRONICS": {
        "return_window_days": 15,
        "is_returnable": True,
        "restocking_fee_rate": 0.10,
    },
    "HOME_GOODS": {
        "return_window_days": 30,
        "is_returnable": True,
        "restocking_fee_rate": 0.05,
    },
    "BEAUTY_PERSONAL_CARE": {
        "return_window_days": 14,
        "is_returnable": True,
        "restocking_fee_rate": 0.00,
    },
    "PERISHABLES_FINAL_SALE": {
        "return_window_days": 0,
        "is_returnable": False,
        "restocking_fee_rate": 0.00,
    },
}

PRODUCT_CATALOG = [
    ("SKU-APP-1001", "Merino Wool Crewneck Sweater", "APPAREL", 85.00),
    ("SKU-APP-1002", "Tailored Chino Trousers", "APPAREL", 68.00),
    ("SKU-APP-1003", "Waterproof Trench Coat", "APPAREL", 165.00),
    ("SKU-APP-1004", "Organic Cotton Oxford Shirt", "APPAREL", 54.00),
    ("SKU-APP-1005", "Lightweight Running Sneakers", "APPAREL", 110.00),
    ("SKU-ELC-2001", "Noise-Cancelling Wireless Headphones", "ELECTRONICS", 249.99),
    ("SKU-ELC-2002", "4K USB-C Docking Station", "ELECTRONICS", 139.50),
    ("SKU-ELC-2003", "Mechanical Tactile Keyboard", "ELECTRONICS", 119.00),
    ("SKU-ELC-2004", "Smart Fitness Watch Pro", "ELECTRONICS", 299.00),
    ("SKU-ELC-2005", "Portable GaN 100W Charger", "ELECTRONICS", 64.99),
    ("SKU-HOM-3001", "Cast Iron Dutch Oven 6Qt", "HOME_GOODS", 129.00),
    ("SKU-HOM-3002", "Belgian Linen Duvet Cover Set", "HOME_GOODS", 175.00),
    ("SKU-HOM-3003", "Pour-Over Precision Coffee Kettle", "HOME_GOODS", 79.00),
    ("SKU-HOM-3004", "Ceramic Table Lamp", "HOME_GOODS", 92.00),
    ("SKU-BTY-4001", "Hyaluronic Acid Hydrating Serum", "BEAUTY_PERSONAL_CARE", 42.00),
    ("SKU-BTY-4002", "Botanical Facial Cleanser", "BEAUTY_PERSONAL_CARE", 28.00),
    ("SKU-BTY-4003", "Mineral SPF 50 Sunscreen", "BEAUTY_PERSONAL_CARE", 34.00),
    ("SKU-PER-5001", "Artisanal Single-Origin Espresso Beans (2lb)", "PERISHABLES_FINAL_SALE", 36.00),
    ("SKU-PER-5002", "Assorted Belgian Truffle Gift Box", "PERISHABLES_FINAL_SALE", 48.00),
    ("SKU-PER-5003", "Clearance Final-Sale Silk Scarf", "PERISHABLES_FINAL_SALE", 29.00),
]

FIRST_NAMES = [
    "Aarav", "Elena", "Marcus", "Priya", "Liam", "Sofia", "Noah", "Ananya",
    "Ethan", "Maya", "Lucas", "Zara", "Mason", "Chloe", "Logan", "Nadia",
    "Caleb", "Hannah", "Owen", "Rohan", "Clara", "Isaac", "Meera", "Julian",
]

LAST_NAMES = [
    "Sharma", "Patel", "Carter", "Nguyen", "Brooks", "Reddy", "Kim", "Reyes",
    "Bennett", "Foster", "Gupta", "Morales", "Hayes", "Nair", "Sullivan", "Chavez",
    "Griffin", "Varma", "Diaz", "Mercer", "Kulkarni", "Walsh", "Silva", "Bhatt",
]

TAX_RATES = [0.00, 0.05, 0.0625, 0.075, 0.0825, 0.095]

def fmt_customer_id(seq: int) -> str:
    return f"CUST-{YEAR_PREFIX}-{seq:06d}"

def fmt_order_id(seq: int) -> str:
    return f"ORD-{YEAR_PREFIX}-{seq:06d}"

def fmt_order_line_id(order_id: str, line_num: int) -> str:
    return f"ORDL-{order_id}-{line_num:02d}"

def fmt_rma_id(seq: int) -> str:
    return f"RMA-{YEAR_PREFIX}-{seq:06d}"

def fmt_return_line_id(rma_id: str, line_num: int) -> str:
    return f"RMAL-{rma_id}-{line_num:02d}"

def fmt_auth_id(seq: int) -> str:
    return f"AUTH-{YEAR_PREFIX}-{seq:06d}"

def fmt_shipment_id(seq: int) -> str:
    return f"RTS-{YEAR_PREFIX}-{seq:06d}"

def fmt_inspection_id(seq: int) -> str:
    return f"INSP-{YEAR_PREFIX}-{seq:06d}"

def fmt_refund_id(seq: int) -> str:
    return f"REF-{YEAR_PREFIX}-{seq:06d}"

def fmt_disposition_id(seq: int) -> str:
    return f"DISP-{YEAR_PREFIX}-{seq:06d}"

def fmt_event_id(seq: int) -> str:
    return f"EVT-{YEAR_PREFIX}-{seq:07d}"

def fmt_anomaly_id(seq: int) -> str:
    return f"ANOM-{YEAR_PREFIX}-{seq:04d}"

def iso_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
