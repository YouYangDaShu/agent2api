#!/usr/bin/env python3
"""Align the old custom report index with upstream schema v15.

Run only on a backup or with the service stopped. Does not set user_version;
Agent2API applies its own schema migration at next startup.
"""
import argparse
import json
import sqlite3
from pathlib import Path

INDEX = "idx_requests_summary"
LEGACY = ["is_test", "ts", "row_id"]
EXPECTED = ["ts", "is_test", "model", "upstream_model", "total_tokens", "cache_read_tokens", "prompt_tokens"]
DDL = "CREATE INDEX idx_requests_summary ON requests(ts, is_test, model, upstream_model, total_tokens, cache_read_tokens, prompt_tokens)"


def align(database: Path) -> dict:
    with sqlite3.connect(database.resolve().as_uri() + "?mode=rw", uri=True, timeout=30) as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = [row[2] for row in conn.execute("PRAGMA index_info(idx_requests_summary)")]
        if current and current not in (LEGACY, EXPECTED):
            raise ValueError(f"Unexpected {INDEX} columns: {current}; refusing to replace")
        before = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("accounts", "requests")}
        if current == LEGACY:
            conn.execute("DROP INDEX idx_requests_summary")
        if current != EXPECTED:
            conn.execute(DDL)
        after = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in before}
        actual = [row[2] for row in conn.execute("PRAGMA index_info(idx_requests_summary)")]
        if before != after or actual != EXPECTED:
            raise RuntimeError("Index alignment verification failed")
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("Database quick_check failed")
        conn.commit()
        return {"previous_columns": current, "columns": actual, "table_counts": after, "changed": current != EXPECTED}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    print(json.dumps(align(args.database), ensure_ascii=False))
