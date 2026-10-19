from datetime import date

from src.sales_analytics.analytics import compute_top_products

def test_top_products_returns_top_five(conn):
    conn.execute(
        "INSERT INTO customers VALUES (1, 'Acme Corp', 'US')"
    )
    conn.execute(
        "INSERT INTO orders VALUES (1, 1, '2025-01-10', 10000.0)"
    )

    conn.executemany(
        """
        INSERT INTO order_items
            (order_item_id, order_id, product_name, quantity, unit_price)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, 1, "Laptop Pro", 3, 2000.0),
            (2, 1, "Monitor", 10, 200.0),
            (3, 1, "Keyboard", 20, 25.0),
            (4, 1, "Mouse", 30, 10.0),
            (5, 1, "Dock", 4, 100.0),
            (6, 1, "Webcam", 2, 50.0),
        ],
    )
    conn.commit()

    result = compute_top_products(conn)

    assert list(result.columns) == ["product_name", "total_revenue"]
    assert len(result) == 5

    assert result["product_name"].tolist() == [
        "Laptop Pro",
        "Monitor",
        "Keyboard",
        "Dock",
        "Mouse",
    ]

    assert result["total_revenue"].tolist() == [
        6000.0,
        2000.0,
        500.0,
        400.0,
        300.0,
    ]


def test_top_products_filters_dates(conn):
    conn.execute(
        "INSERT INTO customers VALUES (1, 'Acme Corp', 'US')"
    )

    conn.executemany(
        """
        INSERT INTO orders
            (order_id, customer_id, order_date, total_amount)
        VALUES (?, ?, ?, ?)
        """,
        [
            (1, 1, "2025-01-31", 1000.0),
            (2, 1, "2025-02-01", 1000.0),
            (3, 1, "2025-02-28", 1000.0),
            (4, 1, "2025-03-01", 1000.0),
        ],
    )

    conn.executemany(
        """
        INSERT INTO order_items
            (order_item_id, order_id, product_name, quantity, unit_price)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, 1, "Laptop", 1, 100.0),  # Before the interval
            (2, 2, "Laptop", 2, 100.0),  # Initial date
            (3, 3, "Laptop", 3, 100.0),  # Final date
            (4, 4, "Laptop", 4, 100.0),  # After the interval
        ],
    )
    conn.commit()

    result = compute_top_products(
        conn,
        from_date=date(2025, 2, 1),
        to_date=date(2025, 2, 28),
    )

    assert list(result.columns) == ["product_name", "total_revenue"]

    assert result.to_dict("records") == [
        {
            "product_name": "Laptop",
            "total_revenue": 500.0,
        }
    ]
