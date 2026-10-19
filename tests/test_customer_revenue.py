from datetime import date

from src.sales_analytics.analytics import compute_revenue_per_customer_month

def test_revenue_per_customer_month(conn):
    conn.execute(
        "INSERT INTO customers VALUES (1, 'Acme Corp', 'US')"
    )
    conn.execute(
        "INSERT INTO customers VALUES (2, 'Beta Ltd', 'UK')"
    )

    conn.executemany(
        """
        INSERT INTO orders
            (order_id, customer_id, order_date, total_amount)
        VALUES (?, ?, ?, ?)
        """,
        [
            (1, 1, "2025-01-10", 1000.0),
            (2, 1, "2025-01-20", 200.0),
            (3, 1, "2025-01-25", -50.0),
            (4, 2, "2025-01-15", 500.0),
            (5, 2, "2025-02-05", 300.0),
        ],
    )
    conn.commit()

    result = compute_revenue_per_customer_month(conn)

    assert list(result.columns) == [
        "customer_id", "name", "country", "year_month", "revenue"
    ]

    assert result.to_dict("records") == [
        {
            "customer_id": 1,
            "name": "Acme Corp",
            "country": "US",
            "year_month": "2025-01",
            "revenue": 1200.0,
        },
        {
            "customer_id": 2,
            "name": "Beta Ltd",
            "country": "UK",
            "year_month": "2025-01",
            "revenue": 500.0,
        },
        {
            "customer_id": 2,
            "name": "Beta Ltd",
            "country": "UK",
            "year_month": "2025-02",
            "revenue": 300.0,
        },
    ]


def test_revenue_per_customer_month_filters_dates(conn):
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
            (1, 1, "2025-01-31", 100.0),  # Before interval
            (2, 1, "2025-02-01", 200.0),  # Initial date
            (3, 1, "2025-02-15", 300.0),  # Within interval
            (5, 1, "2025-03-01", 500.0),  # After interval
            (6, 1, "2025-02-20", -50.0),  # Reimbursement
            (4, 1, "2025-02-28", 400.0),  # Final date
        ],
    )
    conn.commit()

    result = compute_revenue_per_customer_month(
        conn,
        from_date=date(2025, 2, 1),
        to_date=date(2025, 2, 28),
    )

    assert list(result.columns) == [
        "customer_id", "name", "country", "year_month", "revenue"
    ]

    assert result.to_dict("records") == [
        {
            "customer_id": 1,
            "name": "Acme Corp",
            "country": "US",
            "year_month": "2025-02",
            "revenue": 900.0,
        }
    ]
