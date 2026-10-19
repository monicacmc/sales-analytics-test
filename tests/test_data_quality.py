import logging
import sqlite3
import pandas as pd
import pytest

from src.sales_analytics import loaders
from src.sales_analytics.db import create_in_memory_db


@pytest.mark.parametrize(
    "amount",
    [None, "", "  "],
    ids=["null", "empty", "whitespace"],
)
def test_missing_total_amount_becomes_zero(
    conn,
    tmp_path,
    monkeypatch,
    customer_data,
    valid_order_data,
    write_csv,
    amount,
):
    monkeypatch.setattr(loaders, "DATA_DIR", tmp_path)

    write_csv(tmp_path, "customers.csv", customer_data)

    order = {
        **valid_order_data[0],
        "total_amount": amount,
    }
    write_csv(tmp_path, "orders.csv", [order])

    loaders.load_customers(conn)
    loaders.load_orders(conn)

    amount_in_db = conn.execute(
        "SELECT total_amount FROM orders WHERE order_id = 101"
    ).fetchone()[0]

    assert amount_in_db == 0.0


def test_negative_quantity_logs_warning(
    conn,
    tmp_path,
    monkeypatch,
    caplog,
    customer_data,
    valid_order_data,
    write_csv,
):
    monkeypatch.setattr(loaders, "DATA_DIR", tmp_path)

    write_csv(tmp_path, "customers.csv", customer_data)
    write_csv(tmp_path, "orders.csv", valid_order_data)

    loaders.load_customers(conn)
    loaders.load_orders(conn)

    write_csv(
        tmp_path,
        "order_items.csv",
        [
            {
                "order_item_id": 1,
                "order_id": 101,
                "product_name": "Laptop",
                "quantity": -2,
                "unit_price": 100.0,
            }
        ],
    )

    with caplog.at_level(logging.WARNING):
        loaders.load_order_items(conn)

    assert "negative quantities" in caplog.text

    count = conn.execute(
        "SELECT COUNT(*) FROM order_items"
    ).fetchone()[0]

    assert count == 1


def test_order_with_missing_customer_is_skipped(
    conn,
    tmp_path,
    monkeypatch,
    caplog,
    valid_order_data,
    write_csv,
):
    monkeypatch.setattr(loaders, "DATA_DIR", tmp_path)

    invalid_order = {
        **valid_order_data[0],
        "customer_id": 999,
    }
    write_csv(tmp_path, "orders.csv", [invalid_order])

    with caplog.at_level(logging.WARNING):
        loaders.load_orders(conn)

    assert "missing references" in caplog.text

    count = conn.execute(
        "SELECT COUNT(*) FROM orders"
    ).fetchone()[0]

    assert count == 0


def test_order_item_with_missing_order_is_skipped(
    conn,
    tmp_path,
    monkeypatch,
    caplog,
    customer_data,
    valid_order_data,
    write_csv,
):
    monkeypatch.setattr(loaders, "DATA_DIR", tmp_path)

    write_csv(tmp_path, "customers.csv", customer_data)
    write_csv(tmp_path, "orders.csv", valid_order_data)

    loaders.load_customers(conn)
    loaders.load_orders(conn)

    write_csv(
        tmp_path,
        "order_items.csv",
        [
            {
                "order_item_id": 1,
                "order_id": 101,
                "product_name": "Laptop",
                "quantity": 2,
                "unit_price": 100.0,
            },
            {
                "order_item_id": 2,
                "order_id": 999,
                "product_name": "Monitor",
                "quantity": 1,
                "unit_price": 200.0,
            },
        ],
    )

    with caplog.at_level(logging.WARNING):
        loaders.load_order_items(conn)

    assert "missing references" in caplog.text

    items = conn.execute(
        """
        SELECT order_item_id, order_id, product_name
        FROM order_items
        ORDER BY order_item_id
        """
    ).fetchall()

    assert items == [
        (1, 101, "Laptop"),
    ]


def test_write_table_detects_row_count_mismatch(
    conn,
    monkeypatch,
):
    df = pd.DataFrame(
        [
            {
                "customer_id": 1,
                "name": "Acme Corp",
                "country": "US",
            },
            {
                "customer_id": 2,
                "name": "Beta Inc",
                "country": "PT",
            },
        ]
    )

    # Simulates an insertion that loads only one line
    def fake_insert_rows(conn, query, rows):
        conn.executemany(query, list(rows)[:1])

    monkeypatch.setattr(
        loaders,
        "_insert_rows",
        fake_insert_rows,
    )

    with pytest.raises(RuntimeError, match="Expected 2 rows"):
        loaders._write_table(df, "customers", conn)


def test_load_all_data_rolls_back_when_order_items_fail(
    tmp_path,
    monkeypatch,
    customer_data,
    valid_order_data,
    write_csv,
):
    monkeypatch.setattr(loaders, "DATA_DIR", tmp_path)

    write_csv(tmp_path, "customers.csv", customer_data)
    write_csv(tmp_path, "orders.csv", valid_order_data)

    # Duplicate primary key provokes an insertion error
    write_csv(
        tmp_path,
        "order_items.csv",
        [
            {
                "order_item_id": 1,
                "order_id": 101,
                "product_name": "Laptop",
                "quantity": 1,
                "unit_price": 100.0,
            },
            {
                "order_item_id": 1,
                "order_id": 101,
                "product_name": "Mouse",
                "quantity": 2,
                "unit_price": 20.0,
            },
        ],
    )

    conn = create_in_memory_db()

    try:
        with pytest.raises(sqlite3.IntegrityError):
            loaders.load_all_data(conn)

        for table in ("customers", "orders", "order_items"):
            count = conn.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]

            assert count == 0, (
                f"Expected table '{table}' to be empty after rollback"
            )
    finally:
        conn.close()


def test_invalid_order_date_is_rejected(
    conn,
    tmp_path,
    monkeypatch,
    customer_data,
    valid_order_data,
    write_csv,
):
    monkeypatch.setattr(loaders, "DATA_DIR", tmp_path)

    write_csv(tmp_path, "customers.csv", customer_data)

    invalid_order = {
        **valid_order_data[0],
        "order_date": "2026-13-40",
    }
    write_csv(tmp_path, "orders.csv", [invalid_order])

    loaders.load_customers(conn)

    with pytest.raises(ValueError, match="valid dates"):
        loaders.load_orders(conn)

    count = conn.execute(
        "SELECT COUNT(*) FROM orders"
    ).fetchone()[0]

    assert count == 0


def test_not_integer_quantity_is_rejected(
    conn,
    tmp_path,
    monkeypatch,
    customer_data,
    valid_order_data,
    write_csv,
):
    monkeypatch.setattr(loaders, "DATA_DIR", tmp_path)

    write_csv(tmp_path, "customers.csv", customer_data)
    write_csv(tmp_path, "orders.csv", valid_order_data)

    loaders.load_customers(conn)
    loaders.load_orders(conn)

    write_csv(
        tmp_path,
        "order_items.csv",
        [
            {
                "order_item_id": 1,
                "order_id": 101,
                "product_name": "Laptop",
                "quantity": 1.5,
                "unit_price": 100.0,
            }
        ],
    )

    with pytest.raises(ValueError, match="must contain integers"):
        loaders.load_order_items(conn)

    count = conn.execute(
        "SELECT COUNT(*) FROM order_items"
    ).fetchone()[0]

    assert count == 0
