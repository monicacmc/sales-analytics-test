import pandas as pd
import pytest
from src.sales_analytics.db import create_in_memory_db


@pytest.fixture
def conn():
    connection = create_in_memory_db()

    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def customer_data():
    return [
        {
            "customer_id": 1,
            "name": "Ana",
            "country": "Portugal",
        }
    ]


@pytest.fixture
def valid_order_data():
    return [
        {
            "order_id": 101,
            "customer_id": 1,
            "order_date": "2026-01-15",
            "total_amount": 100.0,
        }
    ]


@pytest.fixture
def write_csv():
    def _write_csv(directory, filename, rows):
        pd.DataFrame(rows).to_csv(
            directory / filename,
            index=False,
        )

    return _write_csv
