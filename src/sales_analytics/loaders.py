import logging

from pathlib import Path
from sqlite3 import Connection
import pandas as pd

from .config import DATA_DIR


logger = logging.getLogger(__name__)

TABLE_COLUMNS = {
    "customers": ("customer_id", "name", "country"),
    "orders": (
        "order_id",
        "customer_id",
        "order_date",
        "total_amount",
    ),
    "order_items": (
        "order_item_id",
        "order_id",
        "product_name",
        "quantity",
        "unit_price",
    ),
}

def _insert_rows(
    conn: Connection,
    query: str,
    rows,
) -> None:
    conn.executemany(query, rows)

def _load_csv(filename: str) -> pd.DataFrame:
    """Read a CSV file from DATA_DIR and log errors if reading fails."""
    path = Path(DATA_DIR) / filename
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        logger.error("Failed to read %s: %s", filename, exc)
        raise

def _validate_columns(
    df: pd.DataFrame,
    filename: str,
    table: str,
) -> None:
    """Raise ValueError if the table is unknown or required columns are missing."""
    if table not in TABLE_COLUMNS:
        raise ValueError(f"Unknown table: {table}")

    missing_columns = set(TABLE_COLUMNS[table]) - set(df.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"Invalid CSV '{filename}': "
            f"missing required columns: {missing}"
        )

def _normalize_total_amount(df: pd.DataFrame) -> pd.DataFrame:
    """Replace blank or missing order amounts with 0.0."""
    amounts = df["total_amount"].astype("string")
    amounts = amounts.mask(amounts.str.strip().eq(""), pd.NA)

    missing_count = int(amounts.isna().sum())

    if missing_count:
        logger.warning(
            "Found %d missing total_amount values; replacing with 0.0",
            missing_count,
        )

    try:
        df = df.copy()
        df["total_amount"] = pd.to_numeric(
            amounts,
            errors="raise",
        ).fillna(0.0)
    except (ValueError, TypeError):
        logger.exception("Invalid total_amount values in orders.csv")
        raise

    return df

def _write_table(
    df: pd.DataFrame,
    table: str,
    conn: Connection,
) -> None:
    """Insert rows into a table and verify the inserted row count."""
    if table not in TABLE_COLUMNS:
        raise ValueError(f"Unknown table: {table}")

    columns = TABLE_COLUMNS[table]
    df = df.loc[:, columns]

    columns_sql = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)

    query = (
        f'INSERT INTO "{table}" ({columns_sql}) '
        f"VALUES ({placeholders})"
    )

    try:
        before_insertion = conn.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0]

        rows = df.itertuples(index=False, name=None)

        _insert_rows(conn, query, rows)

        after_insertion = conn.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0]

        count_inserted = after_insertion - before_insertion

        if count_inserted != len(df):
            raise RuntimeError(
                f"Expected {len(df)} rows to be inserted into "
                f"'{table}', but got {count_inserted}"
            )

    except Exception:
        logger.exception(
            "Database loading failed: could not write or validate "
            "table '%s'",
            table,
        )
        raise

    logger.info(
        "Successfully loaded %d rows into table '%s'",
        count_inserted,
        table,
    )

def _filter_missing_foreign_keys(
    df: pd.DataFrame,
    conn: Connection,
    fk_column: str,
    referenced_table: str,
    referenced_column: str,
    entity_name: str,
) -> pd.DataFrame:
    """Skip rows whose foreign key does not exist."""
    existing_ids = {
        row[0]
        for row in conn.execute(
            f'SELECT "{referenced_column}" FROM "{referenced_table}"'
        ).fetchall()
    }

    invalid_fk = ~df[fk_column].isin(existing_ids)

    if invalid_fk.any():
        logger.warning(
            "Found %d %s with missing references; skipping these %s",
            int(invalid_fk.sum()),
            entity_name,
            entity_name,
        )
        df = df.loc[~invalid_fk].copy()

    return df

def _validate_numeric_column(df, column, filename):
    """Ensure a column contains valid numeric values."""
    try:
        values = pd.to_numeric(df[column], errors="raise")
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Column '{column}' in {filename} must contain numeric values"
        ) from exc

    if values.isna().any():
        raise ValueError(
            f"Column '{column}' in {filename} contains missing values"
        )

    df[column] = values

def _validate_integer_column(df, column, filename):
    """Ensure a column contains valid integer values."""
    _validate_numeric_column(df, column, filename)

    values = df[column]

    if (values % 1 != 0).any():
        raise ValueError(
            f"Column '{column}' in {filename} must contain integers"
        )

def _validate_date_column(df, column, filename):
    if df[column].isna().any() or (
        df[column].astype("string").str.strip().eq("").fillna(False).any()
    ):
        raise ValueError(
            f"Column '{column}' in {filename} contains missing dates"
        )

    try:
        df[column] = pd.to_datetime(
            df[column],
            format="%Y-%m-%d",
            errors="raise",
        ).dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Column '{column}' in {filename} "
            "must contain valid dates in YYYY-MM-DD format"
        ) from exc

def load_orders(conn: Connection) -> None:
    """Load orders, replacing blank amounts and checking customer FKs."""
    filename = "orders.csv"
    df = _load_csv(filename)

    _validate_columns(
        df,
        filename,
        "orders"
    )
    _validate_date_column(df, "order_date", filename)

    # Convert blank and null amounts to zero
    df = _normalize_total_amount(df)

    # Check customer foreign keys before inserting orders
    df = _filter_missing_foreign_keys(
        df=df,
        conn=conn,
        fk_column="customer_id",
        referenced_table="customers",
        referenced_column="customer_id",
        entity_name="orders",
    )

    _write_table(df, "orders", conn)

def load_order_items(conn: Connection) -> None:
    """Load order items, warning about negative quantities and invalid FKs."""
    filename = "order_items.csv"
    df = _load_csv(filename)

    _validate_columns(
        df,
        filename,
        "order_items"
    )

    _validate_integer_column(df, "quantity", filename)
    _validate_numeric_column(df, "unit_price", filename)

    # Negative quantities are reported
    negative_quantity = df["quantity"] < 0

    if negative_quantity.any():
        logger.warning(
            "Found %d order items with negative quantities",
            int(negative_quantity.sum()),
        )

    # Check order foreign keys before inserting order items
    df = _filter_missing_foreign_keys(
        df=df,
        conn=conn,
        fk_column="order_id",
        referenced_table="orders",
        referenced_column="order_id",
        entity_name="order items",
    )
    _write_table(df, "order_items", conn)

def load_customers(conn: Connection) -> None:
    """Load customer records from customers.csv into the database."""
    filename = "customers.csv"
    df = _load_csv(filename)
    _validate_columns(
        df,
        filename,
        "customers"
    )
    _write_table(df, "customers", conn)

def load_all_data(conn: Connection) -> None:
    """Load all CSV data in dependency order and commit or roll back."""
    try:
        load_customers(conn)
        load_orders(conn)
        load_order_items(conn)

        conn.commit()

    except Exception:
        conn.rollback()
        logger.exception(
            "Data loading failed; rolling back all changes"
        )
        raise

