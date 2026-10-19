from datetime import date, timedelta
from pathlib import Path
from sqlite3 import Connection
import pandas as pd

def _build_date_filters(
    from_date: date | None,
    to_date: date | None,
    conditions: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Build SQL date conditions and their parameter values."""
    conditions = list(conditions or [])
    params = []

    if from_date is not None:
        conditions.append("o.order_date >= ?")
        params.append(from_date.isoformat())

    if to_date is not None:
        conditions.append("o.order_date < ?")
        params.append((to_date + timedelta(days=1)).isoformat())

    return conditions, params

def compute_revenue_per_customer_month(
    conn: Connection,
    from_date: date | None = None,
    to_date: date | None = None,
) -> pd.DataFrame:
    """Calculate monthly revenue per customer, excluding negative amounts."""
    conditions, params = _build_date_filters(
        from_date,
        to_date,
        ["o.total_amount >= 0"]
    )

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT c.customer_id,
               c.name, 
               c.country, 
               strftime('%Y-%m', o.order_date) AS year_month, 
               SUM(o.total_amount) AS revenue
        FROM customers c 
        JOIN orders o
            ON c.customer_id = o.customer_id
        WHERE {where_clause}
        GROUP BY c.customer_id, year_month
        ORDER by year_month ASC, revenue DESC
    """
    return pd.read_sql_query(query, conn, params=params)

def compute_top_products(
    conn: Connection,
    limit: int = 5,
    from_date: date | None = None,
    to_date: date | None = None
) -> pd.DataFrame:
    """Return products ranked by revenue"""
    conditions, params = _build_date_filters(
        from_date,
        to_date,
    )
    date_filter = ""
    if conditions:
        date_filter = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT product_name, 
               SUM(quantity * unit_price) as total_revenue
        FROM order_items oi
        JOIN orders o
            ON o.order_id = oi.order_id
        {date_filter}
        GROUP BY product_name
        ORDER BY total_revenue DESC
        LIMIT ?
    """
    params.append(limit)
    return pd.read_sql_query(query, conn, params=params)

def generate_reports(
    conn: Connection,
    output_dir: Path,
    from_date: date | None = None,
    to_date: date | None = None
) -> None:
    """Generate the customer revenue and top products CSV reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    df_rev = compute_revenue_per_customer_month(conn, from_date=from_date, to_date=to_date)
    df_rev.to_csv(output_dir / "revenue_per_customer_per_month.csv", index=False, float_format="%.2f")

    df_top = compute_top_products(conn, limit=5, from_date=from_date, to_date=to_date)
    df_top.to_csv(output_dir / "top_products.csv", index=False, float_format="%.2f")
