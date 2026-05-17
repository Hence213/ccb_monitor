#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch BOC wealth-management product details and save them into a daily SQLite DB.

Usage:
  python boc/fetch_boc_product_detail.py CYQWFZQXYJX7DA
  python boc/fetch_boc_product_detail.py --product-id CYQWFZQXYJX7DA --product-id CYQWFZQZSGZ14D3A
  python boc/fetch_boc_product_detail.py --input product_ids.txt
  BOC_COOKIE='webcluster=...' python boc/fetch_boc_product_detail.py CYQWFZQXYJX7DA
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from boc.common import (
    DEFAULT_COOKIE,
    DEFAULT_PRODUCTS_CSV,
    connect_product_detail_db,
    list_entry,
    merge_keyed_list,
    post_boc_method,
    read_json_list,
    read_products_csv,
    response_result,
)

SCRIPT_DIR = Path(__file__).resolve().parent / "database"


def get_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if value is not None and str(value).strip() != "":
        return str(value).strip()
    raise ValueError(f"Missing or empty value for key '{key}' in data: {data}")


def normalize_product(detail: dict[str, Any], response_json: dict[str, Any]) -> dict[str, str]:
    periodTerm = detail.get("periodTerm")
    return {
        "productId": get_text(detail, "productId"),
        "productName": get_text(detail, "productName"),
        "riskLevel": get_text(detail, "riskLevel"),
        "productSize": get_text(detail, "productSize"),
        "indiAmt": get_text(detail, "indiAmt"),
        "indiAmtRem": get_text(detail, "indiAmtRem"),
        "establishDate": get_text(detail, "establishDate"),
        "periodTerm": periodTerm if isinstance(periodTerm, str) else "0",
        "updateDate": get_text(detail, "updateDate"),
        "nav": get_text(detail, "nav"),
        "rawJson": json.dumps(response_json, ensure_ascii=False, separators=(",", ":")),
    }


def fetch_product_detail(
    product_id: str,
    *,
    sub_channel_id: str,
    cookie: str,
    timeout: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    response_json = post_boc_method(
        "PsnxWmpProductDetailQueryOutlay",
        {"productId": product_id, "subChannelId": sub_channel_id, "isNewVersion": "Y"},
        cookie=cookie,
        timeout=timeout,
    )
    return response_json, response_result(response_json)


def fetch_nav_list(
    product_id: str,
    *,
    sub_channel_id: str,
    cookie: str,
    timeout: int,
) -> list[dict[str, str]]:
    response_json = post_boc_method(
        "PsnxWmpHistoryNavQueryOutlay",
        {"productId": product_id, "subChannelId": sub_channel_id, "circle": "3Y"},
        cookie=cookie,
        timeout=timeout,
    )
    result = response_result(response_json)
    rows = result.get("list") if isinstance(result, dict) else []
    if not isinstance(rows, list):
        return []
    return [
        {"updateDate": str(row.get("updateDate", "")).strip(), "nav": str(row.get("nav", "")).strip()}
        for row in rows
        if isinstance(row, dict) and row.get("updateDate") and row.get("nav") is not None
    ]


def connect_db(db_path: Path) -> sqlite3.Connection:
    return connect_product_detail_db(db_path)


def save_product(conn: sqlite3.Connection, product: dict[str, str], nav_list: list[dict[str, str]]) -> None:
    existing = conn.execute(
        """
        SELECT productSize_list, indiAmt_list, indiAmtRem_list, nav_list
        FROM product_details
        WHERE productId = ?
        """,
        (product["productId"],),
    ).fetchone()
    existing_product_size = existing[0] if existing else None
    existing_indi_amt = existing[1] if existing else None
    existing_indi_amt_rem = existing[2] if existing else None
    existing_nav = existing[3] if existing else None

    product_size_list = merge_keyed_list(
        existing_product_size,
        list_entry(product["updateDate"], product["productSize"], "productSize"),
        value_key="productSize",
    )
    indi_amt_list = merge_keyed_list(
        existing_indi_amt,
        list_entry(product["updateDate"], product["indiAmt"], "indiAmt"),
        value_key="indiAmt",
    )
    indi_amt_rem_list = merge_keyed_list(
        existing_indi_amt_rem,
        list_entry(product["updateDate"], product["indiAmtRem"], "indiAmtRem"),
        value_key="indiAmtRem",
    )
    merged_nav_list = merge_keyed_list(
        existing_nav, 
        list_entry(product["updateDate"], product["nav"], "nav"), 
        value_key="nav"
    )

    conn.execute(
        """
        INSERT INTO product_details (
            productId, productName, riskLevel, productSize_list, indiAmt_list,
            indiAmtRem_list, establishDate, periodTerm, nav_list, fetchedAt, rawJson
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(productId) DO UPDATE SET
            productSize_list = excluded.productSize_list,
            indiAmt_list = excluded.indiAmt_list,
            indiAmtRem_list = excluded.indiAmtRem_list,
            periodTerm = excluded.periodTerm,
            nav_list = excluded.nav_list,
            fetchedAt = excluded.fetchedAt,
            rawJson = excluded.rawJson
        """,
        (
            product["productId"],
            product["productName"],
            product["riskLevel"],
            product_size_list,
            indi_amt_list,
            indi_amt_rem_list,
            product["establishDate"],
            product["periodTerm"],
            merged_nav_list,
            datetime.now().isoformat(timespec="seconds"),
            product["rawJson"],
        ),
    )


def nav_value_at_date(nav_list_json: Any, update_date: str) -> str:
    for row in read_json_list(nav_list_json):
        if str(row.get("updateDate", "")).strip() == update_date:
            return str(row.get("nav", "")).strip()
    return ""


def decimal_equal(left: str, right: str) -> bool:
    try:
        return Decimal(left) == Decimal(right)
    except (InvalidOperation, ValueError):
        return left.strip() == right.strip()


def fetch_detail_for_batch(
    product: dict[str, str],
    *,
    sub_channel_id: str,
    cookie: str,
    timeout: int,
) -> tuple[str, dict[str, str] | None, str | None]:
    product_id = product["productId"]
    try:
        response_json, detail = fetch_product_detail(
            product_id,
            sub_channel_id=sub_channel_id,
            cookie=cookie,
            timeout=timeout,
        )
        if not detail:
            return product_id, None, "接口返回中未找到 result/data"
        normalized = normalize_product(detail, response_json)
        return product_id, normalized, None
    except Exception as exc:
        return product_id, None, str(exc)


def batch_update_details(
    *,
    products_csv: Path,
    db_path: Path,
    sub_channel_id: str,
    cookie: str,
    timeout: int,
    workers: int,
) -> tuple[int, int]:
    products = read_products_csv(products_csv)
    print(f"读取产品清单 {products_csv}: {len(products)} 个产品")
    print(f"并行抓取产品详情，workers={workers}")

    fetched: list[dict[str, str]] = []
    fail_count = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                fetch_detail_for_batch,
                product,
                sub_channel_id=sub_channel_id,
                cookie=cookie,
                timeout=timeout,
            )
            for product in products
        ]
        for index, future in enumerate(as_completed(futures), 1):
            product_id, product, error = future.result()
            if error or product is None:
                fail_count += 1
                print(f"[{index}/{len(products)}] 失败 {product_id}: {error}")
                continue
            fetched.append(product)
            print(
                f"[{index}/{len(products)}] 成功 {product_id}: "
                f"日期={product['updateDate']} 净值={product['nav']} 剩余额度={product['indiAmtRem']}"
            )

    conn = connect_db(db_path.resolve())
    try:
        for product in fetched:
            save_product(conn, product, [])
        conn.commit()
    finally:
        conn.close()

    return len(products), len(fetched),


def read_product_ids(input_path: Path | None, product_ids: list[str]) -> list[str]:
    values: list[str] = []
    values.extend(product_ids)

    if input_path:
        text = input_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            values.extend(part.strip() for part in line.replace(",", " ").split())

    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        product_id = value.strip().upper()
        if product_id and product_id not in seen:
            seen.add(product_id)
            normalized.append(product_id)
    return normalized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch BOC product details into a daily SQLite database.")
    parser.add_argument("products", nargs="*", help="Product IDs, for example CYQWFZQXYJX7DA.")
    parser.add_argument("--product-id", action="append", default=[], help="Product ID. Can be used multiple times.")
    parser.add_argument("--input", type=Path, help="Text file containing product IDs, separated by newline, comma, or spaces.")
    parser.add_argument("--db-dir", type=Path, default=SCRIPT_DIR, help="Directory for the daily SQLite DB.")
    parser.add_argument("--db-path", type=Path, help="Explicit SQLite DB path. Overrides --db-dir.")
    parser.add_argument("--products-csv", type=Path, help="CSV product list for parallel batch mode.")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers for --products-csv.")
    parser.add_argument("--sub-channel-id", default="31", help="BOC sub channel ID.")
    parser.add_argument("--cookie", default=os.environ.get("BOC_COOKIE", DEFAULT_COOKIE), help="Cookie header value.")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout seconds.")
    parser.add_argument("--print-raw", action="store_true", help="Print each full API response JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = args.db_path or args.db_dir / "boc_product_detail.db"

    if args.products_csv:
        total, ok_count = batch_update_details(
            products_csv=args.products_csv.resolve(),
            db_path=db_path.resolve(),
            sub_channel_id=args.sub_channel_id,
            cookie=args.cookie,
            timeout=args.timeout,
            workers=max(1, args.workers),
        )
        print(f"已保存 {ok_count}/{total} 条产品详情到 {db_path.resolve()}，失败 {total - ok_count} 条")
        return 0
    return 1
if __name__ == "__main__":
    raise SystemExit(main())
