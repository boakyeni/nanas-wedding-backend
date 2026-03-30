#!/usr/bin/env python3
"""Export every table in the database to a single Excel file, one sheet per table.

Usage:
    python export_db_to_excel.py
    python export_db_to_excel.py --output my_export.xlsx

Requires: pip install pandas openpyxl psycopg2-binary
"""

import os
import argparse
import psycopg2
from psycopg2 import sql
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def get_table_names(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        return [row[0] for row in cur.fetchall()]


def main():
    parser = argparse.ArgumentParser(description="Export DB to Excel")
    parser.add_argument("--output", default="database_export.xlsx", help="Output file name")
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT"),
    )

    tables = get_table_names(conn)
    print(f"Found {len(tables)} tables: {', '.join(tables)}")

    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        for table in tables:
            query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
            df = pd.read_sql(query.as_string(conn), conn)
            sheet_name = table[:31]  # Excel sheet names max 31 chars
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"  Wrote '{sheet_name}' ({len(df)} rows, {len(df.columns)} cols)")

    conn.close()
    print(f"\nDone: {args.output}")


if __name__ == "__main__":
    main()
