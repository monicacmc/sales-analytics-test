from .db import create_in_memory_db
from .loaders import load_all_data
from .analytics import generate_reports
from .parser import parse_args


def main() -> None:
    args = parse_args()
    conn = create_in_memory_db()
    try:
        load_all_data(conn)
        generate_reports(
            conn,
            output_dir=args.output_dir,
            from_date=args.from_date,
            to_date=args.to_date,
        )
    finally:
        conn.close()

if __name__ == "__main__":
    main()
