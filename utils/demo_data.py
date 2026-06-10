# ================================================================
# utils/demo_data.py  —  Demo Dataset Generator
# ================================================================
# Generates a realistic 2-year daily sales dataset with
# seasonal patterns, products, and regional breakdown.
# ================================================================

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

PRODUCTS = ["Laptop Pro", "Wireless Mouse", "USB-C Hub", "Monitor 27\"",
            "Mechanical Keyboard", "Webcam HD", "SSD 1TB", "Headphones X"]

REGIONS  = ["North", "South", "East", "West", "Central"]

CITIES = {
    "North":   ["Chicago", "Minneapolis", "Detroit"],
    "South":   ["Houston", "Atlanta", "Miami"],
    "East":    ["New York", "Boston", "Philadelphia"],
    "West":    ["Los Angeles", "Seattle", "San Francisco"],
    "Central": ["Dallas", "Denver", "Phoenix"],
}

def generate_demo_df(n_days: int = 730, seed: int = 42) -> pd.DataFrame:
    """
    Generate a synthetic daily sales DataFrame.

    Schema:
        date, product, region, city, quantity, unit_price,
        sales, discount, profit, category
    """
    rng = np.random.default_rng(seed)
    rows = []
    start = datetime(2022, 1, 1)

    # Base prices per product
    base_prices = {
        "Laptop Pro":           1299.99,
        "Wireless Mouse":         29.99,
        "USB-C Hub":              49.99,
        "Monitor 27\"":          349.99,
        "Mechanical Keyboard":    89.99,
        "Webcam HD":              79.99,
        "SSD 1TB":                99.99,
        "Headphones X":          149.99,
    }
    categories = {
        "Laptop Pro":           "Computers",
        "Wireless Mouse":       "Peripherals",
        "USB-C Hub":            "Accessories",
        "Monitor 27\"":         "Displays",
        "Mechanical Keyboard":  "Peripherals",
        "Webcam HD":            "Accessories",
        "SSD 1TB":              "Storage",
        "Headphones X":         "Audio",
    }

    for day_offset in range(n_days):
        current_date = start + timedelta(days=day_offset)
        month   = current_date.month
        weekday = current_date.weekday()  # 0=Mon

        # Seasonal multiplier — Q4 peak, summer dip
        seasonal = 1.0
        if month in [11, 12]:  seasonal = 1.5
        elif month in [1, 2]:  seasonal = 0.8
        elif month in [6, 7]:  seasonal = 0.9
        elif month in [3, 4]:  seasonal = 1.1

        # Weekend boost (more online shopping)
        weekend_boost = 1.2 if weekday >= 5 else 1.0

        # Yearly growth trend
        year_factor = 1.0 + 0.15 * (day_offset / 365)

        # Number of transactions this day
        n_tx = rng.integers(8, 25)

        for _ in range(n_tx):
            product  = rng.choice(PRODUCTS)
            region   = rng.choice(REGIONS)
            city     = rng.choice(CITIES[region])
            price    = base_prices[product]
            qty      = int(rng.integers(1, 8))
            discount = round(float(rng.choice([0, 0, 0, 0.05, 0.10, 0.15])), 2)
            noise    = float(rng.normal(1.0, 0.12))
            sales    = round(price * qty * (1 - discount) * seasonal
                             * weekend_boost * year_factor * noise, 2)
            profit   = round(sales * float(rng.uniform(0.15, 0.40)), 2)

            rows.append({
                "date":       current_date.strftime("%Y-%m-%d"),
                "product":    product,
                "category":   categories[product],
                "region":     region,
                "city":       city,
                "quantity":   qty,
                "unit_price": round(price, 2),
                "discount":   discount,
                "sales":      max(0, sales),
                "profit":     max(0, profit),
            })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def get_demo_df() -> pd.DataFrame:
    """Return the cached demo DataFrame."""
    return generate_demo_df()
