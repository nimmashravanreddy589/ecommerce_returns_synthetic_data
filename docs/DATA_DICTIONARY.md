# E-Commerce Returns & RMA Synthetic Dataset — Schema & Data Dictionary

## 1. Entity-Relationship & Cardinality Overview

| Parent Entity | Child Entity | Cardinality | Optionality | Relationship Description |
| :--- | :--- | :--- | :--- | :--- |
| `Customer` | `Order` | `1 : N` | Mandatory child | A customer places 1 or more orders. |
| `Order` | `OrderLine` | `1 : N` | Mandatory child | An order contains 1 to 6 line items. |
| `Order` | `ReturnRequest` | `1 : N` | Optional child | An order may have 0, 1, or multiple return requests (e.g., partial returns). |
| `ReturnRequest` | `ReturnLine` | `1 : N` | Mandatory child | A return request contains 1 or more return lines. |
| `OrderLine` | `ReturnLine` | `1 : N` | Optional child | Each return line maps back to a specific purchased order line. |
| `ReturnRequest` | `ReturnAuthorization` | `1 : 1` | Conditional (1:0..1) | Issued when a request is `APPROVED` or `PARTIALLY_APPROVED` (or policy-overridden). |
| `ReturnAuthorization` | `ReturnShipment` | `1 : N` | Optional child | Usually `1:1`, or `1:0` when customer never ships (`MISSING_SHIPMENT`). |
| `ReturnShipment` | `Inspection` | `1 : N` | Optional child | Warehouse inspects each returned item line upon shipment receipt. |
| `ReturnLine` | `Inspection` | `1 : 1` | Conditional (1:0..1) | Each received return line undergoes 1 physical inspection. |
| `ReturnRequest` | `Refund` | `1 : N` | Optional child | Normally `1:1` once approved/inspected; `1:N` occurs in duplicate refund anomalies. |
| `Inspection` | `InventoryDisposition` | `1 : 1` | Mandatory after inspection | Determines final warehouse action (`RESTOCK`, `REFURBISH`, `QUARANTINE`, `SCRAP`). |
| `All Lifecycle Entities` | `StateEventLog` | `1 : N` | Mandatory audit | Append-only event history recording every state transition without overwriting history. |

*(Note: Many-to-many relationships between `Order` and `ReturnRequest` at the item level are resolved through the bridge/junction entity `ReturnLine`, which links `ReturnRequest` (`rma_id`) and `OrderLine` (`order_line_id`).)*

---

## 2. Deterministic ID & Nomenclature Conventions

| Entity | Format Pattern | Example | Uniqueness & Immutability |
| :--- | :--- | :--- | :--- |
| `Customer` | `CUST-2026-XXXXXX` | `CUST-2026-000001` | Primary Key, 6-digit zero-padded, immutable |
| `Order` | `ORD-2026-XXXXXX` | `ORD-2026-000001` | Primary Key, 6-digit zero-padded, immutable |
| `OrderLine` | `ORDL-<ord-id>-XX` | `ORDL-ORD-2026-000001-01` | Primary Key, 2-digit line index, immutable |
| `ReturnRequest` | `RMA-2026-XXXXXX` | `RMA-2026-000001` | Primary Key, 6-digit zero-padded, immutable |
| `ReturnLine` | `RMAL-<rma-id>-XX` | `RMAL-RMA-2026-000001-01` | Primary Key, 2-digit line index, immutable |
| `ReturnAuthorization` | `AUTH-2026-XXXXXX` | `AUTH-2026-000001` | Primary Key, 6-digit zero-padded, immutable |
| `ReturnShipment` | `RTS-2026-XXXXXX` | `RTS-2026-000001` | Primary Key, 6-digit zero-padded, immutable |
| `Inspection` | `INSP-2026-XXXXXX` | `INSP-2026-000001` | Primary Key, 6-digit zero-padded, immutable |
| `Refund` | `REF-2026-XXXXXX` | `REF-2026-000001` | Primary Key, 6-digit zero-padded, immutable |
| `InventoryDisposition` | `DISP-2026-XXXXXX` | `DISP-2026-000001` | Primary Key, 6-digit zero-padded, immutable |
| `StateEventLog` | `EVT-2026-XXXXXXX` | `EVT-2026-0000001` | Primary Key, 7-digit zero-padded, append-only |

---

## 3. Domain Policy & Business Rules

1. **Category Return Windows & Exclusions:**
   - `APPAREL`: 30 days from `delivered_date` | Returnable: `True` | Restocking Fee: `0%`
   - `ELECTRONICS`: 15 days from `delivered_date` | Returnable: `True` | Restocking Fee: `10%` (if opened/buyer remorse; `0%` if defective)
   - `HOME_GOODS`: 30 days from `delivered_date` | Returnable: `True` | Restocking Fee: `5%` (if buyer remorse)
   - `BEAUTY_PERSONAL_CARE`: 14 days from `delivered_date` | Returnable: `True` (only if unopened/sealed) | Restocking Fee: `0%`
   - `PERISHABLES_FINAL_SALE`: 0 days | Returnable: `False` (`NON_RETURNABLE` exclusion)
2. **Refund Calculation Formula:**
   - `unit_net_paid = (unit_list_price - unit_discount_amount)`
   - `line_net_paid = unit_net_paid * approved_qty`
   - `line_tax_refunded = round(line_net_paid * tax_rate, 2)`
   - `restocking_fee = round(line_net_paid * restocking_fee_rate, 2)` (waived if `return_reason in ['DEFECTIVE', 'WRONG_ITEM_SENT', 'DAMAGED_IN_TRANSIT']`)
   - `refund_amount = round(line_net_paid + line_tax_refunded - restocking_fee, 2)`
3. **Disposition Decision Rules (Post-Inspection):**
   - `NEW_UNOPENED` / `LIKE_NEW` -> `RESTOCK`
   - `MINOR_COSMETIC_DAMAGE` / `OPEN_BOX_ELECTRONICS` -> `REFURBISH`
   - `HYGIENE_SEAL_BROKEN` / `SUSPECTED_FRAUD` -> `QUARANTINE`
   - `HEAVILY_DAMAGED` / `DEFECTIVE_UNREPAIRABLE` -> `SCRAP`

---

## 4. Detailed Field-Level Data Dictionary

### 4.1 `Customer`
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `customer_id` | STRING | Required | `CUST-2026-\d{6}` | ID | Primary Key | Must match regex & be unique |
| `full_name` | STRING | Required | Synthetic full name | Text | Non-unique | Non-empty string |
| `email` | STRING | Required | `user<n>@example.test` | Text | Unique | Valid RFC synthetic email |
| `loyalty_tier` | ENUM | Required | `STANDARD`, `SILVER`, `GOLD`, `VIP` | Category | Non-unique | Must be in allowed enum |
| `account_created_date` | DATE | Required | `YYYY-MM-DD` | ISO Date | Non-unique | `<= first order_date` |
| `return_risk_score` | FLOAT | Required | `0.00` to `1.00` | Score | Non-unique | `0.0 <= val <= 1.0` |
| `is_active` | BOOLEAN | Required | `True`, `False` | Flag | Non-unique | Boolean |

### 4.2 `Order`
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `order_id` | STRING | Required | `ORD-2026-\d{6}` | ID | Primary Key | Must match regex & be unique |
| `customer_id` | STRING | Required | `CUST-2026-\d{6}` | ID | Foreign Key | Must exist in `Customer.customer_id` |
| `order_date` | TIMESTAMP | Required | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | `>= customer.account_created_date` |
| `delivered_date` | TIMESTAMP | Optional | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | `> order_date` when status is `DELIVERED` |
| `currency` | ENUM | Required | `USD` | ISO 4217 | Non-unique | Constant `USD` |
| `order_subtotal` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | Equals `SUM(OrderLine.line_subtotal)` |
| `order_discount_total` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | Equals `SUM(OrderLine.line_discount)` |
| `order_tax_total` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | Equals `SUM(OrderLine.line_tax)` |
| `order_grand_total` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | `subtotal - discount + tax` |
| `order_status` | ENUM | Required | `PLACED`, `SHIPPED`, `DELIVERED`, `CANCELLED` | State | Non-unique | Must be in allowed enum |

### 4.3 `OrderLine`
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `order_line_id` | STRING | Required | `ORDL-ORD-2026-\d{6}-\d{2}` | ID | Primary Key | Must match regex & be unique |
| `order_id` | STRING | Required | `ORD-2026-\d{6}` | ID | Foreign Key | Must exist in `Order.order_id` |
| `sku` | STRING | Required | `SKU-[A-Z]{3}-\d{4}` | Code | Non-unique | Valid catalog SKU |
| `product_name` | STRING | Required | Catalog product title | Text | Non-unique | Non-empty |
| `category` | ENUM | Required | `APPAREL`, `ELECTRONICS`, `HOME_GOODS`, `BEAUTY_PERSONAL_CARE`, `PERISHABLES_FINAL_SALE` | Category | Non-unique | Must be in allowed enum |
| `quantity_ordered` | INTEGER | Required | `1` to `10` | Units | Non-unique | `quantity_ordered >= 1` |
| `unit_list_price` | DECIMAL | Required | `> 0.00` | USD | Non-unique | Positive decimal |
| `unit_discount` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | `0 <= unit_discount < unit_list_price` |
| `tax_rate` | DECIMAL | Required | `0.00` to `0.12` | Ratio | Non-unique | Valid jurisdiction tax rate |
| `line_subtotal` | DECIMAL | Required | `> 0.00` | USD | Non-unique | `round(unit_list_price * quantity_ordered, 2)` |
| `line_discount` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | `round(unit_discount * quantity_ordered, 2)` |
| `line_tax` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | `round((line_subtotal - line_discount) * tax_rate, 2)` |
| `line_paid_total` | DECIMAL | Required | `> 0.00` | USD | Non-unique | `round(line_subtotal - line_discount + line_tax, 2)` |
| `return_window_days` | INTEGER | Required | `0`, `14`, `15`, `30` | Days | Non-unique | Derived from category policy |
| `is_returnable` | BOOLEAN | Required | `True`, `False` | Flag | Non-unique | `False` iff `PERISHABLES_FINAL_SALE` |

### 4.4 `ReturnRequest`
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `rma_id` | STRING | Required | `RMA-2026-\d{6}` | ID | Primary Key | Must match regex & be unique |
| `order_id` | STRING | Required | `ORD-2026-\d{6}` | ID | Foreign Key | Must exist in `Order.order_id` |
| `customer_id` | STRING | Required | `CUST-2026-\d{6}` | ID | Foreign Key | Must match `Order.customer_id` |
| `request_date` | TIMESTAMP | Required | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | `>= Order.delivered_date` |
| `days_since_delivery` | INTEGER | Required | `>= 0` | Days | Non-unique | `(request_date.date() - delivered_date.date()).days` |
| `request_type` | ENUM | Required | `REFUND`, `EXCHANGE`, `STORE_CREDIT` | Category | Non-unique | Must be in allowed enum |
| `policy_override_flag` | BOOLEAN | Required | `True`, `False` | Flag | Non-unique | `True` if late request was manually approved |
| `request_status` | ENUM | Required | `SUBMITTED`, `APPROVED`, `PARTIALLY_APPROVED`, `REJECTED`, `CANCELLED`, `COMPLETED` | State | Non-unique | Driven by line eligibility & workflow |

### 4.5 `ReturnLine`
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `return_line_id` | STRING | Required | `RMAL-RMA-2026-\d{6}-\d{2}` | ID | Primary Key | Must match regex & be unique |
| `rma_id` | STRING | Required | `RMA-2026-\d{6}` | ID | Foreign Key | Must exist in `ReturnRequest.rma_id` |
| `order_line_id` | STRING | Required | `ORDL-ORD-2026-\d{6}-\d{2}` | ID | Foreign Key | Must exist in `OrderLine.order_line_id` |
| `requested_qty` | INTEGER | Required | `>= 1` | Units | Non-unique | Normally `<= remaining returnable qty` (except anomaly) |
| `approved_qty` | INTEGER | Required | `>= 0` | Units | Non-unique | `0 <= approved_qty <= requested_qty` |
| `return_reason` | ENUM | Required | `SIZE_FIT`, `DEFECTIVE`, `DAMAGED_IN_TRANSIT`, `CHANGED_MIND`, `WRONG_ITEM_SENT`, `NOT_AS_DESCRIBED` | Category | Non-unique | Must be in allowed enum |
| `line_status` | ENUM | Required | `PENDING`, `APPROVED`, `REJECTED_POLICY_WINDOW`, `REJECTED_NON_RETURNABLE`, `REJECTED_EXCESS_QTY` | State | Non-unique | Derived from policy rules |
| `expected_refund_amount` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | Derived from `approved_qty`, paid price, tax, & fee |

### 4.6 `ReturnAuthorization`
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `auth_id` | STRING | Required | `AUTH-2026-\d{6}` | ID | Primary Key | Must match regex & be unique |
| `rma_id` | STRING | Required | `RMA-2026-\d{6}` | ID | Foreign Key (Unique) | Must exist in `ReturnRequest.rma_id` |
| `authorized_date` | TIMESTAMP | Required | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | `>= ReturnRequest.request_date` |
| `expiration_date` | TIMESTAMP | Required | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | `authorized_date + 14 days` |
| `return_warehouse_code` | ENUM | Required | `WH-EAST-01`, `WH-WEST-02`, `WH-CENTRAL-03` | Code | Non-unique | Valid warehouse facility |
| `auth_status` | ENUM | Required | `ISSUED`, `USED`, `EXPIRED`, `VOIDED` | State | Non-unique | Must be in allowed enum |

### 4.7 `ReturnShipment`
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `shipment_id` | STRING | Required | `RTS-2026-\d{6}` | ID | Primary Key | Must match regex & be unique |
| `rma_id` | STRING | Required | `RMA-2026-\d{6}` | ID | Foreign Key | Must exist in `ReturnRequest.rma_id` |
| `auth_id` | STRING | Required | `AUTH-2026-\d{6}` | ID | Foreign Key | Must exist in `ReturnAuthorization.auth_id` |
| `carrier` | ENUM | Required | `UPS`, `FEDEX`, `USPS`, `DHL` | Carrier | Non-unique | Must be in allowed enum |
| `tracking_number` | STRING | Required | `1Z[A-Z0-9]{14}` | Code | Unique | Unique tracking identifier |
| `shipped_date` | TIMESTAMP | Optional | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | `>= authorized_date` (Null if `LABEL_CREATED_NOT_SHIPPED`) |
| `received_date` | TIMESTAMP | Optional | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | `>= shipped_date` when `DELIVERED_TO_WAREHOUSE` |
| `shipment_status` | ENUM | Required | `LABEL_CREATED_NOT_SHIPPED`, `IN_TRANSIT`, `DELIVERED_TO_WAREHOUSE`, `LOST_IN_TRANSIT` | State | Non-unique | Must be in allowed enum |

### 4.8 `Inspection`
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `inspection_id` | STRING | Required | `INSP-2026-\d{6}` | ID | Primary Key | Must match regex & be unique |
| `shipment_id` | STRING | Required | `RTS-2026-\d{6}` | ID | Foreign Key | Must exist in `ReturnShipment.shipment_id` |
| `return_line_id` | STRING | Required | `RMAL-RMA-2026-\d{6}-\d{2}` | ID | Foreign Key (Unique) | Must exist in `ReturnLine.return_line_id` |
| `inspected_date` | TIMESTAMP | Required | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | `>= ReturnShipment.received_date` |
| `inspector_id` | STRING | Required | `EMP-\d{4}` | ID | Non-unique | Warehouse QA technician ID |
| `condition_grade` | ENUM | Required | `NEW_UNOPENED`, `LIKE_NEW`, `OPEN_BOX_ELECTRONICS`, `MINOR_COSMETIC_DAMAGE`, `HYGIENE_SEAL_BROKEN`, `HEAVILY_DAMAGED`, `DEFECTIVE_UNREPAIRABLE` | Grade | Non-unique | Must be in allowed enum |
| `inspection_result` | ENUM | Required | `PASS`, `PASS_WITH_FEE`, `FAIL_DAMAGED`, `FAIL_SEAL_BROKEN` | State | Non-unique | Must be in allowed enum |

### 4.9 `Refund`
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `refund_id` | STRING | Required | `REF-2026-\d{6}` | ID | Primary Key | Must match regex & be unique |
| `rma_id` | STRING | Required | `RMA-2026-\d{6}` | ID | Foreign Key | Must exist in `ReturnRequest.rma_id` |
| `order_id` | STRING | Required | `ORD-2026-\d{6}` | ID | Foreign Key | Must match `ReturnRequest.order_id` |
| `refund_date` | TIMESTAMP | Required | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | `>= Inspection.inspected_date` (or `authorized_date` for instant refund) |
| `refund_method` | ENUM | Required | `ORIGINAL_PAYMENT`, `STORE_CREDIT`, `EXCHANGE_CREDIT` | Method | Non-unique | Must be in allowed enum |
| `gross_items_refund` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | Sum of approved net paid line amounts |
| `tax_refunded` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | Sum of approved line taxes |
| `restocking_fee_deducted` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | Sum of applicable restocking fees |
| `net_refund_amount` | DECIMAL | Required | `>= 0.00` | USD | Non-unique | `gross_items_refund + tax_refunded - restocking_fee_deducted` |
| `refund_status` | ENUM | Required | `PENDING`, `PROCESSED`, `FAILED`, `BLOCKED_DUPLICATE` | State | Non-unique | Must be in allowed enum |

### 4.10 `InventoryDisposition`
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `disposition_id` | STRING | Required | `DISP-2026-\d{6}` | ID | Primary Key | Must match regex & be unique |
| `inspection_id` | STRING | Optional | `INSP-2026-\d{6}` | ID | Foreign Key | Required for valid flow (Null in `RESTOCK_BEFORE_INSPECTION` anomaly) |
| `return_line_id` | STRING | Required | `RMAL-RMA-2026-\d{6}-\d{2}` | ID | Foreign Key | Must exist in `ReturnLine.return_line_id` |
| `disposition_date` | TIMESTAMP | Required | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | Normally `>= Inspection.inspected_date` |
| `disposition_action` | ENUM | Required | `RESTOCK`, `REFURBISH`, `QUARANTINE`, `SCRAP` | Action | Non-unique | Driven by `Inspection.condition_grade` |
| `quantity_processed` | INTEGER | Required | `>= 1` | Units | Non-unique | Must equal `ReturnLine.approved_qty` |
| `target_bin_location` | STRING | Required | `BIN-[A-Z]{2}-\d{3}` | Location | Non-unique | Warehouse bin code |

### 4.11 `StateEventLog` (Append-Only Audit Trail)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `event_id` | STRING | Required | `EVT-2026-\d{7}` | ID | Primary Key | Unique, monotonically increasing |
| `entity_type` | ENUM | Required | `ORDER`, `RETURN_REQUEST`, `RETURN_AUTH`, `RETURN_SHIPMENT`, `INSPECTION`, `REFUND`, `DISPOSITION` | Entity | Non-unique | Must be in allowed enum |
| `entity_id` | STRING | Required | Parent entity primary key | ID | Non-unique | Must exist in target entity table |
| `from_state` | STRING | Optional | Previous lifecycle state or `NULL` | State | Non-unique | `NULL` on initial creation |
| `to_state` | STRING | Required | New lifecycle state | State | Non-unique | Non-empty valid state |
| `event_timestamp` | TIMESTAMP | Required | `YYYY-MM-DDTHH:MM:SSZ` | ISO UTC | Non-unique | Non-decreasing per `entity_id` |
| `actor` | STRING | Required | `SYSTEM_POLICY_ENGINE`, `CUSTOMER`, `CARRIER_WEBHOOK`, `QA_INSPECTOR`, `FINANCE_BATCH`, `MANUAL_OVERRIDE_AGENT` | Actor | Non-unique | Must be in allowed enum |

### 4.12 `GroundTruthAnomaly` (Isolated Evaluation Labels — Never Leaked to Input Features)
| Field | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `anomaly_id` | STRING | Required | `ANOM-2026-\d{4}` | ID | Primary Key | Unique |
| `issue_type` | ENUM | Required | `RETURN_QTY_EXCEEDS_PURCHASED`, `REFUND_EXCEEDS_PAID`, `RESTOCK_BEFORE_INSPECTION`, `LATE_RETURN_NO_OVERRIDE`, `DUPLICATE_REFUND` | Label | Non-unique | Matches the 5 required negative scenarios |
| `primary_entity_type` | ENUM | Required | `RETURN_LINE`, `REFUND`, `INVENTORY_DISPOSITION`, `RETURN_REQUEST` | Entity | Non-unique | Target table containing the anomaly |
| `primary_entity_id` | STRING | Required | Primary key of affected record | ID | Non-unique | Must exist in target table |
| `rma_id` | STRING | Required | `RMA-2026-\d{6}` | ID | Foreign Key | Parent RMA for traceability |
| `order_id` | STRING | Required | `ORD-2026-\d{6}` | ID | Foreign Key | Parent Order for traceability |
| `expected_rule_violated` | STRING | Required | Rule identifier & explanation | Text | Non-unique | Clear audit description |
| `expected_system_action` | ENUM | Required | `BLOCK_RETURN_LINE`, `BLOCK_OVER_REFUND`, `REJECT_PREMATURE_RESTOCK`, `REJECT_OUT_OF_WINDOW`, `BLOCK_DUPLICATE_PAYOUT` | Action | Non-unique | Expected automated control action |