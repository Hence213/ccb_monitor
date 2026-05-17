#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers for BOC wealth-management scripts."""

from __future__ import annotations

import csv
import json
import random
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
DATABASE_DIR = SCRIPT_DIR / "database"
DEFAULT_PRODUCTS_CSV = DATABASE_DIR / "boc_products.csv"
DEFAULT_DB_PATH = DATABASE_DIR / "boc_product_detail.db"
BOC_URL_BASE = "https://ebsnew.boc.cn/BMPS/_bfwajax.do"
DEFAULT_COOKIE = "webcluster=244689a35eac10439a78a059ba4ab8c3"
DEFAULT_NAV_COOKIE = (
    "webcluster=244689a35eac10439a78a059ba4ab8c3; "
    "webcluster=d27f814012c5239d99b97a5ffd5c47a1; "
    "JSESSIONID=06A1DFA101685221D36018CC470D05EF"
)

MOBILE_HEADERS = {
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

PRODUCT_DETAIL_COLUMNS = [
    "productId",
    "productName",
    "riskLevel",
    "productSize_list",
    "indiAmt_list",
    "indiAmtRem_list",
    "establishDate",
    "periodTerm",
    "nav_list",
    "fetchedAt",
    "rawJson",
]


def build_boc_url() -> str:
    rnd = random.SystemRandom().randint(1000, 99999999)
    return f"{BOC_URL_BASE}?rnd={rnd}&_locale=zh_CN"


def mobile_header(uuid: str | None = None) -> dict[str, str]:
    return {
        "agent": "X-ANDR",
        "version": "3.1.9",
        "device": "android",
        "platform": "android",
        "plugins": "5",
        "page": "6",
        "local": "zh_CN",
        "uuid": uuid or str(random.SystemRandom().randint(10**20, 10**21 - 1)),
        "ext": "8",
        "cipherType": "0",
        "appSequence": "",
    }


def build_mobile_payload(method: str, params: dict[str, Any], uuid: str | None = None) -> dict[str, Any]:
    return {"header": mobile_header(uuid), "method": method, "params": params}


def post_boc_method(
    method: str,
    params: dict[str, Any],
    *,
    cookie: str = "",
    timeout: int = 20,
    headers: dict[str, str] | None = None,
    uuid: str | None = None,
) -> dict[str, Any]:
    request_headers = dict(headers or MOBILE_HEADERS)
    if cookie:
        request_headers["Cookie"] = cookie
    payload = build_mobile_payload(method, params, uuid=uuid)
    resp = requests.post(
        build_boc_url(),
        headers=request_headers,
        data={"json": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


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


def extract_nav_list(response_json: Any) -> list[dict[str, Any]]:
    if isinstance(response_json, list):
        return [row for row in response_json if isinstance(row, dict)]
    if not isinstance(response_json, dict):
        return []

    result = response_json.get("result")
    if isinstance(result, dict) and isinstance(result.get("list"), list):
        return [row for row in result["list"] if isinstance(row, dict)]
    if isinstance(result, list):
        return [row for row in result if isinstance(row, dict)]

    response = response_json.get("response")
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, dict) and isinstance(data.get("navList"), list):
            return [row for row in data["navList"] if isinstance(row, dict)]
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]

    data = response_json.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict) and isinstance(data.get("navList"), list):
        return [row for row in data["navList"] if isinstance(row, dict)]
    return []


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


def merge_keyed_list(existing: Any, additions: list[dict[str, str]], *, value_key: str) -> str:
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


def ensure_product_detail_schema(conn: sqlite3.Connection) -> None:
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
            periodTerm TEXT NOT NULL DEFAULT '0',
            nav_list TEXT NOT NULL DEFAULT '[]',
            fetchedAt TEXT NOT NULL,
            rawJson TEXT NOT NULL
        )
        """
    )


def migrate_product_details_schema(conn: sqlite3.Connection) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(product_details)").fetchall()]
    if columns == PRODUCT_DETAIL_COLUMNS:
        return

    conn.execute("ALTER TABLE product_details RENAME TO product_details_old")
    ensure_product_detail_schema(conn)
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
                str(row.get("periodTerm") or result.get("periodTerm") or "0").strip() or "0",
                merge_keyed_list(row.get("nav_list"), list_entry(update_date, nav, "nav"), value_key="nav"),
                row.get("fetchedAt") or datetime.now().isoformat(timespec="seconds"),
                raw_json,
            ),
        )
    conn.execute("DROP TABLE product_details_old")
    conn.commit()


def connect_product_detail_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    ensure_product_detail_schema(conn)
    migrate_product_details_schema(conn)
    return conn
