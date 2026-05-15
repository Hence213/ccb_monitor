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
import csv
import json
import os
import random
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import requests

# 放到data目录下
SCRIPT_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_PRODUCTS_CSV = SCRIPT_DIR / "boc_products.csv"
BOC_URL_BASE = "https://ebsnew.boc.cn/BMPS/_bfwajax.do"
DEFAULT_COOKIE = "webcluster=244689a35eac10439a78a059ba4ab8c3"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 9; 2410DPN6CC Build/PQ3B.190801.03251327; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 "
        "Mobile Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
    "Content-Type": "application/x-www-form-urlencoded",
    "bfw-ctrl": "json",
    "Origin": "https://ebsnew.boc.cn",
    "X-Requested-With": "com.android.browser",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://ebsnew.boc.cn/preview/bocphone/VueLocalCli4/bocFinanceDetail/index.html",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


def build_boc_url() -> str:
    rnd = random.SystemRandom().randint(1000, 99999999)
    return f"{BOC_URL_BASE}?rnd={rnd}&_locale=zh_CN"


def build_payload(product_id: str, sub_channel_id: str) -> dict[str, Any]:
    return {
        "header": {
            "agent": "X-ANDR",
            "version": "3.1.9",
            "device": "android",
            "platform": "android",
            "plugins": "5",
            "page": "6",
            "local": "zh_CN",
            "uuid": str(random.SystemRandom().randint(10**20, 10**21 - 1)),
            "ext": "8",
            "cipherType": "0",
            "appSequence": "",
        },
        "method": "PsnxWmpProductDetailQueryOutlay",
        "params": {
            "productId": product_id,
            "subChannelId": sub_channel_id,
            "isNewVersion": "Y",
        },
    }


def build_nav_payload(product_id: str, sub_channel_id: str) -> dict[str, Any]:
    payload = build_payload(product_id, sub_channel_id)
    payload["method"] = "PsnxWmpHistoryNavQueryOutlay"
    payload["params"] = {
        "productId": product_id,
        "subChannelId": sub_channel_id,
        "circle": "3Y",
    }
    return payload


def response_result(response_json: Any) -> dict[str, Any]:
    if not isinstance(response_json, dict):
        return {}
    result = response_json.get("result")
    if isinstance(result, dict):
        return result
    data = response_json.get("data")
    if isinstance(data, dict):
        return data
    response = response_json.get("response")
    if isinstance(response, dict) and isinstance(response.get("data"), dict):
        return response["data"]
    return {}


def first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def normalize_product(product_id: str, detail: dict[str, Any], response_json: dict[str, Any]) -> dict[str, str]:
    update_date = first_text(detail, ("updateDate", "fundNavDate", "workday")) or datetime.now().strftime("%Y/%m/%d")
    return {
        "productId": first_text(detail, ("productId", "prodCode")) or product_id,
        "productName": first_text(detail, ("productName", "productShortName", "productLongName", "prodName")),
        "riskLevel": first_text(detail, ("riskLevel", "riskLevelDisplay", "riskLevelName", "riskGrade")),
        "productSize": first_text(detail, ("productSize", "prodSize", "raiseSize", "totalScale")),
        "indiAmt": first_text(detail, ("indiAmt", "totalIndiAmt", "quota", "amountLimit")),
        "indiAmtRem": first_text(detail, ("indiAmtRem", "remainIndiAmt", "remainQuota", "availableAmount")),
        "establishDate": first_text(detail, ("establishDate", "productEstablishDate", "setupDate", "startDate")),
        "periodTerm": first_text(detail, ("periodTerm", "dayPerPeriod", "redeemDays")) or "1",
        "updateDate": update_date,
        "nav": first_text(detail, ("nav", "netValue", "unitNav")),
        "rawJson": json.dumps(response_json, ensure_ascii=False, separators=(",", ":")),
    }


def fetch_product_detail(
    product_id: str,
    *,
    sub_channel_id: str,
    cookie: str,
    timeout: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    headers = dict(HEADERS)
    if cookie:
        headers["Cookie"] = cookie

    payload = build_payload(product_id, sub_channel_id)
    resp = requests.post(
        build_boc_url(),
        headers=headers,
        data={"json": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
        timeout=timeout,
    )
    resp.raise_for_status()
    response_json = resp.json()
    return response_json, response_result(response_json)


def fetch_nav_list(
    product_id: str,
    *,
    sub_channel_id: str,
    cookie: str,
    timeout: int,
) -> list[dict[str, str]]:
    headers = dict(HEADERS)
    if cookie:
        headers["Cookie"] = cookie

    payload = build_nav_payload(product_id, sub_channel_id)
    resp = requests.post(
        build_boc_url(),
        headers=headers,
        data={"json": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
        timeout=timeout,
    )
    resp.raise_for_status()
    response_json = resp.json()
    result = response_result(response_json)
    rows = result.get("list") if isinstance(result, dict) else []
    if not isinstance(rows, list):
        return []
    return [
        {"updateDate": str(row.get("updateDate", "")).strip(), "nav": str(row.get("nav", "")).strip()}
        for row in rows
        if isinstance(row, dict) and row.get("updateDate") and row.get("nav") is not None
    ]


def read_json_list(value: Any) -> list[dict[str, str]]:
    if not value:
        return []
    if isinstance(value, list):
        rows = value
    else:
        try:
            rows = json.loads(str(value))
        except json.JSONDecodeError:
            return []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def merge_keyed_list(
    existing: Any,
    additions: list[dict[str, str]],
    *,
    value_key: str,
) -> str:
    merged: dict[str, dict[str, str]] = {}
    for row in [*read_json_list(existing), *additions]:
        update_date = str(row.get("updateDate", "")).strip()
        value = row.get(value_key)
        if not update_date or value is None or str(value).strip() == "":
            continue
        merged[update_date] = {"updateDate": update_date, value_key: str(value).strip()}
    rows = [merged[key] for key in sorted(merged)]
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def list_entry(update_date: str, value: str, value_key: str) -> list[dict[str, str]]:
    if not update_date or not value:
        return []
    return [{"updateDate": update_date, value_key: value}]


def connect_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS product_details (
            productId TEXT PRIMARY KEY,
            productName TEXT,
            riskLevel TEXT,
            productSize_list TEXT NOT NULL DEFAULT '[]',
            indiAmt_list TEXT NOT NULL DEFAULT '[]',
            indiAmtRem_list TEXT NOT NULL DEFAULT '[]',
            establishDate TEXT,
            periodTerm TEXT NOT NULL DEFAULT '1',
            nav_list TEXT NOT NULL DEFAULT '[]',
            fetchedAt TEXT NOT NULL,
            rawJson TEXT NOT NULL
        )
        """
    )
    migrate_product_details_schema(conn)
    return conn


def migrate_product_details_schema(conn: sqlite3.Connection) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(product_details)").fetchall()]
    expected = [
        "productId", "productName", "riskLevel", "productSize_list", "indiAmt_list",
        "indiAmtRem_list", "establishDate", "periodTerm", "nav_list", "fetchedAt", "rawJson",
    ]
    if columns == expected:
        return

    conn.execute("ALTER TABLE product_details RENAME TO product_details_old")
    conn.execute(
        """
        CREATE TABLE product_details (
            productId TEXT PRIMARY KEY,
            productName TEXT,
            riskLevel TEXT,
            productSize_list TEXT NOT NULL DEFAULT '[]',
            indiAmt_list TEXT NOT NULL DEFAULT '[]',
            indiAmtRem_list TEXT NOT NULL DEFAULT '[]',
            establishDate TEXT,
            periodTerm TEXT NOT NULL DEFAULT '1',
            nav_list TEXT NOT NULL DEFAULT '[]',
            fetchedAt TEXT NOT NULL,
            rawJson TEXT NOT NULL
        )
        """
    )
    old_rows = conn.execute("SELECT * FROM product_details_old").fetchall()
    old_columns = [row[1] for row in conn.execute("PRAGMA table_info(product_details_old)").fetchall()]
    for old_row in old_rows:
        row = dict(zip(old_columns, old_row))
        raw_json = row.get("rawJson") or "{}"
        try:
            raw = json.loads(raw_json)
        except json.JSONDecodeError:
            raw = {}
        result = raw.get("result") if isinstance(raw, dict) else {}
        if not isinstance(result, dict):
            result = {}
        update_date = (
            str(result.get("updateDate") or result.get("fundNavDate") or "").strip()
            or str(row.get("fetchedAt") or "")[:10].replace("-", "/")
            or datetime.now().strftime("%Y/%m/%d")
        )
        nav = str(result.get("nav") or "").strip()
        conn.execute(
            """
            INSERT INTO product_details (
                productId, productName, riskLevel, productSize_list, indiAmt_list,
                indiAmtRem_list, establishDate, periodTerm, nav_list, fetchedAt, rawJson
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("productId"),
                row.get("productName"),
                row.get("riskLevel"),
                merge_keyed_list(row.get("productSize_list"), list_entry(update_date, str(row.get("productSize") or ""), "productSize"), value_key="productSize"),
                merge_keyed_list(row.get("indiAmt_list"), list_entry(update_date, str(row.get("indiAmt") or ""), "indiAmt"), value_key="indiAmt"),
                merge_keyed_list(row.get("indiAmtRem_list"), list_entry(update_date, str(row.get("indiAmtRem") or ""), "indiAmtRem"), value_key="indiAmtRem"),
                row.get("establishDate"),
                str(row.get("periodTerm") or result.get("periodTerm") or "1").strip() or "1",
                merge_keyed_list(row.get("nav_list"), list_entry(update_date, nav, "nav"), value_key="nav"),
                row.get("fetchedAt") or datetime.now().isoformat(timespec="seconds"),
                raw_json,
            ),
        )
    conn.execute("DROP TABLE product_details_old")
    conn.commit()


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
    merged_nav_list = merge_keyed_list(existing_nav, nav_list, value_key="nav")

    conn.execute(
        """
        INSERT INTO product_details (
            productId, productName, riskLevel, productSize_list, indiAmt_list,
            indiAmtRem_list, establishDate, periodTerm, nav_list, fetchedAt, rawJson
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(productId) DO UPDATE SET
            productName = excluded.productName,
            riskLevel = excluded.riskLevel,
            productSize_list = excluded.productSize_list,
            indiAmt_list = excluded.indiAmt_list,
            indiAmtRem_list = excluded.indiAmtRem_list,
            establishDate = excluded.establishDate,
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


def read_products_csv(products_csv: Path) -> list[dict[str, str]]:
    with products_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        products: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in reader:
            product_id = (row.get("产品代码") or "").strip().upper()
            if not product_id or product_id in seen:
                continue
            seen.add(product_id)
            products.append(
                {
                    "productId": product_id,
                    "productName": (row.get("产品名称") or "").strip(),
                    "riskLevel": (row.get("风险等级") or "").strip(),
                }
            )
        return products


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
        normalized = normalize_product(product_id, detail, response_json)
        if not normalized["productName"]:
            normalized["productName"] = product.get("productName", "")
        if not normalized["riskLevel"]:
            normalized["riskLevel"] = product.get("riskLevel", "")
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
) -> tuple[int, int, int, list[dict[str, str]]]:
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
    mismatches: list[dict[str, str]] = []
    try:
        for product in fetched:
            existing = conn.execute(
                "SELECT nav_list FROM product_details WHERE productId = ?",
                (product["productId"],),
            ).fetchone()
            db_nav = nav_value_at_date(existing[0] if existing else None, product["updateDate"])
            detail_nav = product.get("nav", "")
            if detail_nav and db_nav and not decimal_equal(detail_nav, db_nav):
                mismatches.append(
                    {
                        "productId": product["productId"],
                        "updateDate": product["updateDate"],
                        "detailNav": detail_nav,
                        "dbNav": db_nav,
                    }
                )
            elif detail_nav and not db_nav:
                mismatches.append(
                    {
                        "productId": product["productId"],
                        "updateDate": product["updateDate"],
                        "detailNav": detail_nav,
                        "dbNav": "",
                    }
                )
            save_product(conn, product, [])
        conn.commit()
    finally:
        conn.close()

    return len(products), len(fetched), fail_count, mismatches


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
        total, ok_count, fail_count, mismatches = batch_update_details(
            products_csv=args.products_csv.resolve(),
            db_path=db_path.resolve(),
            sub_channel_id=args.sub_channel_id,
            cookie=args.cookie,
            timeout=args.timeout,
            workers=max(1, args.workers),
        )
        print(f"已保存 {ok_count}/{total} 条产品详情到 {db_path.resolve()}，失败 {fail_count} 条")
        if mismatches:
            print(f"nav同日期不一致/缺失 {len(mismatches)} 条:")
            for item in mismatches[:50]:
                print(
                    f"  {item['productId']} {item['updateDate']} "
                    f"详情nav={item['detailNav']} DB nav={item['dbNav'] or '缺失'}"
                )
            if len(mismatches) > 50:
                print(f"  ... 还有 {len(mismatches) - 50} 条")
        else:
            print("nav同日期值对照一致。")
        return 0 if fail_count == 0 and not mismatches else 1

    product_ids = read_product_ids(args.input, [*args.products, *args.product_id])
    if not product_ids:
        raise SystemExit("请提供至少一个 productId，或使用 --input 指定产品代码文件。")

    conn = connect_db(db_path.resolve())
    ok_count = 0

    try:
        for product_id in product_ids:
            try:
                response_json, detail = fetch_product_detail(
                    product_id,
                    sub_channel_id=args.sub_channel_id,
                    cookie=args.cookie,
                    timeout=args.timeout,
                )
                if args.print_raw:
                    print(json.dumps(response_json, ensure_ascii=False, indent=2))
                if not detail:
                    print(f"[失败] {product_id}: 接口返回中未找到 result/data")
                    continue

                product = normalize_product(product_id, detail, response_json)
                nav_list = fetch_nav_list(
                    product["productId"],
                    sub_channel_id=args.sub_channel_id,
                    cookie=args.cookie,
                    timeout=args.timeout,
                )
                save_product(conn, product, nav_list)
                conn.commit()
                ok_count += 1
                print(
                    f"[成功] {product['productId']} {product['productName']} "
                    f"风险={product['riskLevel']} 剩余额度={product['indiAmtRem']} 净值={len(nav_list)}条"
                )
            except Exception as exc:
                print(f"[失败] {product_id}: {exc}")
    finally:
        conn.close()

    print(f"已保存 {ok_count}/{len(product_ids)} 条产品详情到 {db_path.resolve()}")
    return 0 if ok_count == len(product_ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
