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
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
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
    return {
        "productId": first_text(detail, ("productId", "prodCode")) or product_id,
        "productName": first_text(detail, ("productName", "productShortName", "productLongName", "prodName")),
        "riskLevel": first_text(detail, ("riskLevel", "riskLevelDisplay", "riskLevelName", "riskGrade")),
        "productSize": first_text(detail, ("productSize", "prodSize", "raiseSize", "totalScale")),
        "indiAmt": first_text(detail, ("indiAmt", "totalIndiAmt", "quota", "amountLimit")),
        "indiAmtRem": first_text(detail, ("indiAmtRem", "remainIndiAmt", "remainQuota", "availableAmount")),
        "establishDate": first_text(detail, ("establishDate", "productEstablishDate", "setupDate", "startDate")),
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


def db_path_for_today(db_dir: Path) -> Path:
    return db_dir / f"boc_product_detail_{datetime.now().strftime('%Y-%m-%d')}.db"


def connect_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS product_details (
            productId TEXT PRIMARY KEY,
            productName TEXT,
            riskLevel TEXT,
            productSize TEXT,
            indiAmt TEXT,
            indiAmtRem TEXT,
            establishDate TEXT,
            subChannelId TEXT,
            fetchedAt TEXT NOT NULL,
            rawJson TEXT NOT NULL
        )
        """
    )
    return conn


def save_product(conn: sqlite3.Connection, product: dict[str, str], sub_channel_id: str) -> None:
    conn.execute(
        """
        INSERT INTO product_details (
            productId, productName, riskLevel, productSize, indiAmt, indiAmtRem,
            establishDate, subChannelId, fetchedAt, rawJson
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(productId) DO UPDATE SET
            productName = excluded.productName,
            riskLevel = excluded.riskLevel,
            productSize = excluded.productSize,
            indiAmt = excluded.indiAmt,
            indiAmtRem = excluded.indiAmtRem,
            establishDate = excluded.establishDate,
            subChannelId = excluded.subChannelId,
            fetchedAt = excluded.fetchedAt,
            rawJson = excluded.rawJson
        """,
        (
            product["productId"],
            product["productName"],
            product["riskLevel"],
            product["productSize"],
            product["indiAmt"],
            product["indiAmtRem"],
            product["establishDate"],
            sub_channel_id,
            datetime.now().isoformat(timespec="seconds"),
            product["rawJson"],
        ),
    )


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
    parser.add_argument("--sub-channel-id", default="31", help="BOC sub channel ID.")
    parser.add_argument("--cookie", default=os.environ.get("BOC_COOKIE", DEFAULT_COOKIE), help="Cookie header value.")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout seconds.")
    parser.add_argument("--print-raw", action="store_true", help="Print each full API response JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    product_ids = read_product_ids(args.input, [*args.products, *args.product_id])
    if not product_ids:
        raise SystemExit("请提供至少一个 productId，或使用 --input 指定产品代码文件。")

    db_path = args.db_path or db_path_for_today(args.db_dir)
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
                save_product(conn, product, args.sub_channel_id)
                conn.commit()
                ok_count += 1
                print(
                    f"[成功] {product['productId']} {product['productName']} "
                    f"风险={product['riskLevel']} 剩余额度={product['indiAmtRem']}"
                )
            except Exception as exc:
                print(f"[失败] {product_id}: {exc}")
    finally:
        conn.close()

    print(f"已保存 {ok_count}/{len(product_ids)} 条产品详情到 {db_path.resolve()}")
    return 0 if ok_count == len(product_ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
