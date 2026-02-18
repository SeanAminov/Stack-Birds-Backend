"""
Reference data extracted from: Stackbirds_Assignment_Invoice_Extract_100_Rows.xlsx

Each (vendor, item) stores raw price points from that vendor's invoices only.
No cross-vendor mixing. Single-invoice vendors have 1 data point, not a fake range.
"""

# ── Approved Vendors ────────────────────────────────────────────────
APPROVED_VENDORS = {
    "Acme Supplies Inc.": [
        "acme supplies", "acme supplies inc", "acme supplies inc.",
        "acme supply",
    ],
    "BrightOffice LLC": [
        "brightoffice llc", "brightoffice", "bright office llc",
        "bright office", "bright-office",
    ],
    "Harbor Hardware": [
        "harbor hardware", "harbour hardware", "harbor hw",
    ],
    "Northstar IT Services": [
        "northstar it services", "northstar it", "northstar",
        "north star it", "north star it services",
    ],
    "Citywide Maintenance": [
        "citywide maintenance", "citywide",
        "city wide maintenance", "city-wide maintenance",
    ],
    "Orbit Software Ltd.": [
        "orbit software ltd.", "orbit software ltd",
        "orbit software", "orbit",
    ],
    "Pioneer Logistics Co.": [
        "pioneer logistics co.", "pioneer logistics co",
        "pioneer logistics", "pioneer",
    ],
    "GreenFields Produce": [
        "greenfields produce", "greenfields",
        "green fields produce", "green fields",
    ],
    "Zenith Catering Group Inc": [
        "zenith catering group inc", "zenith catering group",
        "zenith catering", "zenith", "zcg",
    ],
}

# ── Price History (VERIFIED from Excel, per-vendor, per-item) ──────
# Each entry = one line from one invoice. Raw data, no aggregation.
#
# Acme Supplies Inc. — 3 invoices (INV-20250003, INV-20250011, INV-20250018)
# BrightOffice LLC — 2 invoices (INV-20250001, INV-20250015)
# Harbor Hardware — 5 invoices (INV-20250002, INV-20250008, INV-20250013, INV-20250014, INV-20250017)
# Northstar IT Services — 5 invoices (INV-20250005, INV-20250006, INV-20250009, INV-20250010, INV-20250020)
# Citywide Maintenance — 2 invoices (INV-20250007, INV-20250012)
# Orbit Software Ltd. — 1 invoice (INV-20250004)
# Pioneer Logistics Co. — 1 invoice (INV-20250016)
# GreenFields Produce — 1 invoice (INV-20250019)
# Zenith Catering Group Inc — 0 invoices (no history)

PRICE_HISTORY = {
    # ── Acme Supplies Inc. (3 invoices) ──────────────────────────
    ("Acme Supplies Inc.", "A4 Paper Box"): [
        {"price": 88.72, "qty": 24, "invoice": "INV-20250003"},
        {"price": 24.19, "qty": 35, "invoice": "INV-20250011"},
        {"price": 84.99, "qty": 29, "invoice": "INV-20250018"},
    ],
    ("Acme Supplies Inc.", "Notebooks (Set of 10)"): [
        {"price": 94.69, "qty": 41, "invoice": "INV-20250003"},
        {"price": 118.77, "qty": 16, "invoice": "INV-20250011"},
        {"price": 23.97, "qty": 50, "invoice": "INV-20250018"},
    ],
    ("Acme Supplies Inc.", "Pens (Box)"): [
        {"price": 38.05, "qty": 43, "invoice": "INV-20250003"},
        {"price": 88.55, "qty": 37, "invoice": "INV-20250011"},
        {"price": 86.33, "qty": 28, "invoice": "INV-20250018"},
    ],
    ("Acme Supplies Inc.", "Printer Toner Model X"): [
        {"price": 15.09, "qty": 46, "invoice": "INV-20250003"},
        {"price": 32.61, "qty": 27, "invoice": "INV-20250011"},
        {"price": 15.91, "qty": 8,  "invoice": "INV-20250018"},
    ],
    ("Acme Supplies Inc.", "Staples Pack"): [
        {"price": 147.86, "qty": 19, "invoice": "INV-20250003"},
        {"price": 75.39,  "qty": 43, "invoice": "INV-20250011"},
        {"price": 28.43,  "qty": 17, "invoice": "INV-20250018"},
    ],

    # ── BrightOffice LLC (2 invoices) ────────────────────────────
    ("BrightOffice LLC", "Monitor Arm"): [
        {"price": 190.35, "qty": 44, "invoice": "INV-20250001"},
        {"price": 66.98,  "qty": 17, "invoice": "INV-20250015"},
    ],
    ("BrightOffice LLC", "Ergonomic Chair Rental"): [
        {"price": 40.00, "qty": 140, "invoice": "INV-20250001"},
        {"price": 38.86, "qty": 159, "invoice": "INV-20250015"},
    ],
    ("BrightOffice LLC", "Standing Desk Rental"): [
        {"price": 27.31, "qty": 109, "invoice": "INV-20250001"},
        {"price": 92.77, "qty": 134, "invoice": "INV-20250015"},
    ],
    ("BrightOffice LLC", "Cable Management Kit"): [
        {"price": 70.29, "qty": 6,  "invoice": "INV-20250001"},
        {"price": 92.26, "qty": 46, "invoice": "INV-20250015"},
    ],
    ("BrightOffice LLC", "Keyboard + Mouse Set"): [
        {"price": 158.46, "qty": 33, "invoice": "INV-20250001"},
        {"price": 154.24, "qty": 43, "invoice": "INV-20250015"},
    ],

    # ── Harbor Hardware (5 invoices) ─────────────────────────────
    ("Harbor Hardware", "Safety Gloves"): [
        {"price": 162.13, "qty": 49, "invoice": "INV-20250002"},
        {"price": 26.81,  "qty": 2,  "invoice": "INV-20250008"},
        {"price": 185.67, "qty": 17, "invoice": "INV-20250013"},
        {"price": 16.89,  "qty": 35, "invoice": "INV-20250014"},
        {"price": 44.70,  "qty": 22, "invoice": "INV-20250017"},
    ],
    ("Harbor Hardware", "Ladder Rental"): [
        {"price": 87.41,  "qty": 45, "invoice": "INV-20250002"},
        {"price": 184.11, "qty": 34, "invoice": "INV-20250008"},
        {"price": 37.10,  "qty": 4,  "invoice": "INV-20250013"},
        {"price": 117.94, "qty": 4,  "invoice": "INV-20250014"},
        {"price": 58.11,  "qty": 10, "invoice": "INV-20250017"},
    ],
    ("Harbor Hardware", "Drill Bits Set"): [
        {"price": 35.32,  "qty": 18, "invoice": "INV-20250002"},
        {"price": 190.93, "qty": 35, "invoice": "INV-20250008"},
        {"price": 197.14, "qty": 1,  "invoice": "INV-20250013"},
        {"price": 35.70,  "qty": 34, "invoice": "INV-20250014"},
        {"price": 149.77, "qty": 7,  "invoice": "INV-20250017"},
    ],
    ("Harbor Hardware", "Fasteners Assortment"): [
        {"price": 70.64,  "qty": 49, "invoice": "INV-20250002"},
        {"price": 68.21,  "qty": 39, "invoice": "INV-20250008"},
        {"price": 173.61, "qty": 14, "invoice": "INV-20250013"},
        {"price": 97.97,  "qty": 38, "invoice": "INV-20250014"},
        {"price": 27.51,  "qty": 17, "invoice": "INV-20250017"},
    ],
    ("Harbor Hardware", "Tools Rental"): [
        {"price": 79.09,  "qty": 6,  "invoice": "INV-20250002"},
        {"price": 153.69, "qty": 24, "invoice": "INV-20250008"},
        {"price": 99.70,  "qty": 27, "invoice": "INV-20250013"},
        {"price": 16.15,  "qty": 21, "invoice": "INV-20250014"},
        {"price": 46.07,  "qty": 39, "invoice": "INV-20250017"},
    ],

    # ── Northstar IT Services (5 invoices) ───────────────────────
    ("Northstar IT Services", "Security Audit"): [
        {"price": 116.94, "qty": 103, "invoice": "INV-20250005"},
        {"price": 177.38, "qty": 36,  "invoice": "INV-20250006"},
        {"price": 155.78, "qty": 156, "invoice": "INV-20250009"},
        {"price": 162.87, "qty": 133, "invoice": "INV-20250010"},
        {"price": 77.02,  "qty": 180, "invoice": "INV-20250020"},
    ],
    ("Northstar IT Services", "Helpdesk Support"): [
        {"price": 278.28, "qty": 55, "invoice": "INV-20250005"},
        {"price": 248.02, "qty": 41, "invoice": "INV-20250006"},
        {"price": 82.10,  "qty": 33, "invoice": "INV-20250009"},
        {"price": 51.80,  "qty": 57, "invoice": "INV-20250010"},
        {"price": 89.80,  "qty": 69, "invoice": "INV-20250020"},
    ],
    ("Northstar IT Services", "Network Troubleshooting"): [
        {"price": 269.09, "qty": 146, "invoice": "INV-20250005"},
        {"price": 238.95, "qty": 24,  "invoice": "INV-20250006"},
        {"price": 286.71, "qty": 122, "invoice": "INV-20250009"},
        {"price": 106.17, "qty": 64,  "invoice": "INV-20250010"},
        {"price": 252.69, "qty": 189, "invoice": "INV-20250020"},
    ],
    ("Northstar IT Services", "Software License Admin"): [
        {"price": 103.16, "qty": 81,  "invoice": "INV-20250005"},
        {"price": 104.83, "qty": 93,  "invoice": "INV-20250006"},
        {"price": 183.18, "qty": 195, "invoice": "INV-20250009"},
        {"price": 55.26,  "qty": 87,  "invoice": "INV-20250010"},
        {"price": 250.56, "qty": 106, "invoice": "INV-20250020"},
    ],
    ("Northstar IT Services", "Laptop Setup"): [
        {"price": 148.91, "qty": 32, "invoice": "INV-20250005"},
        {"price": 88.21,  "qty": 8,  "invoice": "INV-20250006"},
        {"price": 116.26, "qty": 11, "invoice": "INV-20250009"},
        {"price": 107.53, "qty": 36, "invoice": "INV-20250010"},
        {"price": 281.12, "qty": 48, "invoice": "INV-20250020"},
    ],

    # ── Citywide Maintenance (2 invoices) ────────────────────────
    ("Citywide Maintenance", "Plumbing Repair"): [
        {"price": 318.32, "qty": 175, "invoice": "INV-20250007"},
        {"price": 275.26, "qty": 104, "invoice": "INV-20250012"},
    ],
    ("Citywide Maintenance", "Light Fixture Replacement"): [
        {"price": 148.38, "qty": 49, "invoice": "INV-20250007"},
        {"price": 222.48, "qty": 13, "invoice": "INV-20250012"},
    ],
    ("Citywide Maintenance", "Trash Removal"): [
        {"price": 168.55, "qty": 42, "invoice": "INV-20250007"},
        {"price": 191.02, "qty": 9,  "invoice": "INV-20250012"},
    ],
    ("Citywide Maintenance", "Office Cleaning"): [
        {"price": 194.56, "qty": 19, "invoice": "INV-20250007"},
        {"price": 143.38, "qty": 7,  "invoice": "INV-20250012"},
    ],
    ("Citywide Maintenance", "HVAC Check"): [
        {"price": 75.89,  "qty": 30, "invoice": "INV-20250007"},
        {"price": 202.22, "qty": 18, "invoice": "INV-20250012"},
    ],

    # ── Orbit Software Ltd. (1 invoice) ──────────────────────────
    ("Orbit Software Ltd.", "Priority Support"): [
        {"price": 140.82, "qty": 172, "invoice": "INV-20250004"},
    ],
    ("Orbit Software Ltd.", "Additional Seats"): [
        {"price": 327.54, "qty": 175, "invoice": "INV-20250004"},
    ],
    ("Orbit Software Ltd.", "Implementation Fee"): [
        {"price": 321.14, "qty": 156, "invoice": "INV-20250004"},
    ],
    ("Orbit Software Ltd.", "API Overages"): [
        {"price": 367.27, "qty": 35, "invoice": "INV-20250004"},
    ],
    ("Orbit Software Ltd.", "SaaS Subscription"): [
        {"price": 236.51, "qty": 42, "invoice": "INV-20250004"},
    ],

    # ── Pioneer Logistics Co. (1 invoice) ────────────────────────
    ("Pioneer Logistics Co.", "Storage Fee"): [
        {"price": 219.68, "qty": 19, "invoice": "INV-20250016"},
    ],
    ("Pioneer Logistics Co.", "Local Delivery"): [
        {"price": 113.43, "qty": 33, "invoice": "INV-20250016"},
    ],
    ("Pioneer Logistics Co.", "Freight Handling"): [
        {"price": 353.54, "qty": 90, "invoice": "INV-20250016"},
    ],
    ("Pioneer Logistics Co.", "Packing Materials"): [
        {"price": 154.12, "qty": 16, "invoice": "INV-20250016"},
    ],
    ("Pioneer Logistics Co.", "Express Delivery"): [
        {"price": 180.89, "qty": 11, "invoice": "INV-20250016"},
    ],

    # ── GreenFields Produce (1 invoice) ──────────────────────────
    ("GreenFields Produce", "Eggs (Dozen)"): [
        {"price": 15.86, "qty": 20, "invoice": "INV-20250019"},
    ],
    ("GreenFields Produce", "Fruit Assortment"): [
        {"price": 36.16, "qty": 3, "invoice": "INV-20250019"},
    ],
    ("GreenFields Produce", "Organic Salad Mix"): [
        {"price": 27.92, "qty": 54, "invoice": "INV-20250019"},
    ],
    ("GreenFields Produce", "Seasonal Veg Box"): [
        {"price": 5.91, "qty": 43, "invoice": "INV-20250019"},
    ],
    ("GreenFields Produce", "Herbs Bundle"): [
        {"price": 23.28, "qty": 50, "invoice": "INV-20250019"},
    ],

    # ── Zenith Catering Group Inc — NO historical invoice data ───
    # Approved vendor, but zero price history.
}

# ── Item Aliases ────────────────────────────────────────────────────
ITEM_ALIASES = {
    "standing desk rental - nov":   "Standing Desk Rental",
    "standing desk rental":         "Standing Desk Rental",
    "ergonomic chair rental-nov":   "Ergonomic Chair Rental",
    "ergonomic chair rental":       "Ergonomic Chair Rental",
    "cable mgmt kit":               "Cable Management Kit",
    "cable management kit":         "Cable Management Kit",
    "a4 paper box":                 "A4 Paper Box",
    "printer toner model x":        "Printer Toner Model X",
    "staples pack":                 "Staples Pack",
    "monitor arm":                  "Monitor Arm",
    "keyboard + mouse set":         "Keyboard + Mouse Set",
    "keyboard and mouse set":       "Keyboard + Mouse Set",
    "safety gloves":                "Safety Gloves",
    "ladder rental":                "Ladder Rental",
    "drill bits set":               "Drill Bits Set",
    "fasteners assortment":         "Fasteners Assortment",
    "tools rental":                 "Tools Rental",
    "notebooks (set of 10)":        "Notebooks (Set of 10)",
    "pens (box)":                   "Pens (Box)",
    "security audit":               "Security Audit",
    "helpdesk support":             "Helpdesk Support",
    "network troubleshooting":      "Network Troubleshooting",
    "software license admin":       "Software License Admin",
    "laptop setup":                 "Laptop Setup",
    "plumbing repair":              "Plumbing Repair",
    "light fixture replacement":    "Light Fixture Replacement",
    "trash removal":                "Trash Removal",
    "office cleaning":              "Office Cleaning",
    "hvac check":                   "HVAC Check",
    "priority support":             "Priority Support",
    "additional seats":             "Additional Seats",
    "implementation fee":           "Implementation Fee",
    "api overages":                 "API Overages",
    "saas subscription":            "SaaS Subscription",
    "storage fee":                  "Storage Fee",
    "local delivery":               "Local Delivery",
    "freight handling":             "Freight Handling",
    "packing materials":            "Packing Materials",
    "express delivery":             "Express Delivery",
    "eggs (dozen)":                 "Eggs (Dozen)",
    "fruit assortment":             "Fruit Assortment",
    "organic salad mix":            "Organic Salad Mix",
    "seasonal veg box":             "Seasonal Veg Box",
    "herbs bundle":                 "Herbs Bundle",
    "corporate lunch buffet":       "Corporate Lunch Buffet",
    "corporate lunch buffet (45 ppl)": "Corporate Lunch Buffet",
    "beverage package":             "Beverage Package",
    "vegetarian add-on":            "Vegetarian Add-on",
    "vegetarian addon":             "Vegetarian Add-on",
}

# ── Policies ────────────────────────────────────────────────────────

PRICE_RANGE_BUFFER = 0.15  # 15% buffer beyond observed min/max

# Strict price ratio thresholds (relative to historical avg).
# invoice_price / avg > 1.5 → OVERPRICED (hard flag)
# invoice_price / avg < 0.75 → UNDERPRICED (hard flag)
MAX_PRICE_RATIO_HIGH = 1.5
MAX_PRICE_RATIO_LOW = 0.75

# Tax rates seen in historical data (computed from Excel: tax / subtotal per invoice).
# Tax is an OBSERVATION, not a gate — different rates are valid.
VALID_TAX_RATES = [0.0, 0.075, 0.0825, 0.095]
TAX_TOLERANCE = 0.005  # 0.5pp tolerance

# Shipping: max seen per vendor from Excel. Observation only.
SHIPPING_MAX_SEEN = {
    "Acme Supplies Inc.":        60.00,   # seen: $0, $60, $40
    "BrightOffice LLC":          60.00,   # seen: $60, $25
    "Harbor Hardware":           40.00,   # seen: $15, $15, $15, $0, $40
    "Northstar IT Services":     40.00,   # seen: $0, $40, $40, $0, $25
    "Citywide Maintenance":      40.00,   # seen: $40, $25
    "Orbit Software Ltd.":       60.00,   # seen: $60
    "Pioneer Logistics Co.":     40.00,   # seen: $40
    "GreenFields Produce":       40.00,   # seen: $40
    "Zenith Catering Group Inc": 60.00,   # no data; conservative estimate
}
