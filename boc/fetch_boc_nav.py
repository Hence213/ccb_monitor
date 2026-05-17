#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch BOC wealth-management NAV history and embed it into nav_annualized_chart.html.

Usage:
  python boc/fetch_boc_nav.py
  python boc/fetch_boc_nav.py --product-id WFZQQQPZRKA
  BOC_COOKIE='webcluster=...; JSESSIONID=...' python boc/fetch_boc_nav.py
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from boc.common import (
    DEFAULT_DB_PATH,
    DEFAULT_NAV_COOKIE as DEFAULT_COOKIE,
    DEFAULT_PRODUCTS_CSV,
    MOBILE_HEADERS,
    connect_product_detail_db,
    extract_nav_list,
    merge_keyed_list,
    post_boc_method,
    read_products_csv,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_HTML_PATH = SCRIPT_DIR / "nav_annualized_chart.html"
EMBED_START = '<script id="embeddedNavData" type="application/json">'
EMBED_END = "</script>"


def fetch_nav(product_id: str, circle: str, sub_channel_id: str, cookie: str, timeout: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    response_json = post_boc_method(
        "PsnxWmpHistoryNavQueryOutlay",
        {"productId": product_id, "subChannelId": sub_channel_id, "circle": circle},
        cookie=cookie,
        timeout=timeout,
        headers=MOBILE_HEADERS,
        uuid="177842367864015718698",
    )
    nav_list = extract_nav_list(response_json)
    return response_json, nav_list


def json_for_script(data: dict[str, Any]) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return text.replace("</", "<\\/")


def embed_data(html_path: Path, embedded_data: dict[str, Any]) -> None:
    html = html_path.read_text(encoding="utf-8")
    block = f"{EMBED_START}\n{json_for_script(embedded_data)}\n{EMBED_END}"

    start = html.find(EMBED_START)
    if start != -1:
        end = html.find(EMBED_END, start)
        if end == -1:
            raise RuntimeError("Found embedded data start marker but no closing </script>.")
        end += len(EMBED_END)
        html = html[:start] + block + html[end:]
    else:
        main_script = "<script>\nvar processed"
        insert_at = html.find(main_script)
        if insert_at == -1:
            raise RuntimeError("Could not find main chart script insertion point.")
        html = html[:insert_at] + block + "\n\n" + html[insert_at:]

    html_path.write_text(html, encoding="utf-8")


def normalize_nav_rows(nav_list: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in nav_list:
        update_date = str(row.get("updateDate", "")).strip()
        nav = str(row.get("nav", "")).strip()
        if update_date and nav:
            rows.append({"updateDate": update_date, "nav": nav})
    return rows


def merge_nav_list(existing: Any, additions: list[dict[str, str]]) -> str:
    return merge_keyed_list(existing, additions, value_key="nav")


def upsert_product_shells(conn: sqlite3.Connection, products: list[dict[str, str]], fetched_at: str) -> None:
    conn.executemany(
        """
        INSERT INTO product_details (
            productId, productName, riskLevel, productSize_list, indiAmt_list,
            indiAmtRem_list, establishDate, periodTerm, nav_list, fetchedAt, rawJson
        ) VALUES (?, ?, ?, '[]', '[]', '[]', '', '1', '[]', ?, '{}')
        ON CONFLICT(productId) DO UPDATE SET
            productName = COALESCE(NULLIF(excluded.productName, ''), product_details.productName),
            riskLevel = COALESCE(NULLIF(excluded.riskLevel, ''), product_details.riskLevel),
            fetchedAt = excluded.fetchedAt
        """,
        [(item["productId"], item["productName"], item["riskLevel"], fetched_at) for item in products],
    )


def save_nav_to_db(
    db_path: Path,
    products: list[dict[str, str]],
    nav_by_product: dict[str, list[dict[str, str]]],
) -> None:
    fetched_at = datetime.now().isoformat(timespec="seconds")
    conn = connect_product_detail_db(db_path)
    try:
        upsert_product_shells(conn, products, fetched_at)
        for product_id, nav_rows in nav_by_product.items():
            existing = conn.execute(
                "SELECT nav_list FROM product_details WHERE productId = ?",
                (product_id,),
            ).fetchone()
            merged_nav = merge_nav_list(existing[0] if existing else None, nav_rows)
            conn.execute(
                """
                UPDATE product_details
                SET nav_list = ?, fetchedAt = ?
                WHERE productId = ?
                """,
                (merged_nav, fetched_at, product_id),
            )
        conn.commit()
    finally:
        conn.close()


def fetch_nav_for_db_item(
    product: dict[str, str],
    *,
    circle: str,
    sub_channel_id: str,
    cookie: str,
    timeout: int,
) -> tuple[str, list[dict[str, str]], str | None]:
    product_id = product["productId"]
    try:
        _, nav_list = fetch_nav(
            product_id=product_id,
            circle=circle,
            sub_channel_id=sub_channel_id,
            cookie=cookie,
            timeout=timeout,
        )
        return product_id, normalize_nav_rows(nav_list), None
    except Exception as exc:
        return product_id, [], str(exc)


def update_db_nav_lists(
    *,
    products_csv: Path,
    db_path: Path,
    circle: str,
    sub_channel_id: str,
    cookie: str,
    timeout: int,
    workers: int,
) -> tuple[int, int, int]:
    products = read_products_csv(products_csv)
    nav_by_product: dict[str, list[dict[str, str]]] = {}
    fail_count = 0

    print(f"读取产品清单 {products_csv}: {len(products)} 个产品")
    print(f"并行抓取净值，workers={workers}, circle={circle}")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                fetch_nav_for_db_item,
                product,
                circle=circle,
                sub_channel_id=sub_channel_id,
                cookie=cookie,
                timeout=timeout,
            )
            for product in products
        ]
        for index, future in enumerate(as_completed(futures), 1):
            product_id, nav_rows, error = future.result()
            if error:
                fail_count += 1
                print(f"[{index}/{len(products)}] 失败 {product_id}: {error}")
                continue
            nav_by_product[product_id] = nav_rows
            print(f"[{index}/{len(products)}] 成功 {product_id}: {len(nav_rows)} 条")

    save_nav_to_db(db_path, products, nav_by_product)
    return len(products), len(nav_by_product), fail_count


def refresh_html_data(
    product_id: str,
    *,
    circle: str = "3Y",
    sub_channel_id: str = "31",
    html_path: Path = DEFAULT_HTML_PATH,
    cookie: str = DEFAULT_COOKIE,
    timeout: int = 20,
    raw_output: Path | None = None,
    print_response: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    response_json, nav_list = fetch_nav(
        product_id=product_id,
        circle=circle,
        sub_channel_id=sub_channel_id,
        cookie=cookie,
        timeout=timeout,
    )

    if not nav_list:
        preview = json.dumps(response_json, ensure_ascii=False)[:1000]
        raise RuntimeError(f"BOC API returned no NAV records. Response preview: {preview}")

    if print_response:
        print("BOC API response JSON:")
        print(json.dumps(response_json, ensure_ascii=False, indent=2))

    embedded_data = {
        "productId": product_id,
        "circle": circle,
        "subChannelId": sub_channel_id,
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "data": nav_list,
    }
    embed_data(html_path.resolve(), embedded_data)

    if raw_output:
        raw_output.resolve().write_text(
            json.dumps(response_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return response_json, nav_list, embedded_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch BOC NAV history and fill nav_annualized_chart.html.")
    parser.add_argument("--product-id", default="WFZQQQPZRKA", help="BOC product ID.")
    parser.add_argument("--circle", default="3Y", help="Query circle, for example 3Y.")
    parser.add_argument("--sub-channel-id", default="31", help="BOC sub channel ID.")
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML_PATH, help="HTML file to update.")
    parser.add_argument("--cookie", default=os.environ.get("BOC_COOKIE", DEFAULT_COOKIE), help="Cookie header value.")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout seconds.")
    parser.add_argument("--raw-output", type=Path, help="Optional path to save the full API response JSON.")
    parser.add_argument("--update-db", action="store_true", help="Batch fetch products CSV and update DB nav_list.")
    parser.add_argument("--products-csv", type=Path, default=DEFAULT_PRODUCTS_CSV, help="CSV product list for --update-db.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="SQLite DB path for --update-db.")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers for --update-db.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.update_db:
        total, success, fail_count = update_db_nav_lists(
            products_csv=args.products_csv.resolve(),
            db_path=args.db_path.resolve(),
            circle=args.circle,
            sub_channel_id=args.sub_channel_id,
            cookie=args.cookie,
            timeout=args.timeout,
            workers=max(1, args.workers),
        )
        print(f"DB更新完成: 产品 {total} 个，成功 {success} 个，失败 {fail_count} 个，DB={args.db_path.resolve()}")
        return 0 if fail_count == 0 else 1

    product_id = args.product_id.strip().upper()
    _, nav_list, embedded_data = refresh_html_data(
        product_id=product_id,
        circle=args.circle,
        sub_channel_id=args.sub_channel_id,
        html_path=args.html,
        cookie=args.cookie,
        timeout=args.timeout,
        raw_output=args.raw_output,
        print_response=True,
    )

    print(f"Fetched {len(nav_list)} records for {product_id}.")
    print(f"Updated {args.html.resolve()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
