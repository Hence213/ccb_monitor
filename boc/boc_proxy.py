#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中银理财产品API代理服务器 (Flask版)
解决前端直接调用API的CORS问题

运行方式:
  pip install flask  (如果还没有)
  python boc_proxy.py
然后访问: http://127.0.0.1:8080/nav?code=WFZQQQPZRKA

API实际返回格式:
  {"result": {"recordNumber": "208", "list": [{"updateDate":"2025/06/27","nav":"1.00000000",...}]}}
"""

from flask import Flask, request, jsonify, make_response, send_file
import requests
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from boc.common import (
    DEFAULT_DB_PATH,
    DEFAULT_NAV_COOKIE as DEFAULT_COOKIE,
    MOBILE_HEADERS,
    extract_nav_list,
    post_boc_method,
)
from boc.fetch_boc_nav import DEFAULT_HTML_PATH, refresh_html_data

app = Flask(__name__)
PORT = int(os.environ.get('BOC_PROXY_PORT', '8082'))
DEFAULT_DETAIL_URL = (
    "https://ebsnew.boc.cn/preview/bocphone/VueLocalCli4/bocFinanceDetail/index.html"
    "#/productDetail?functionCode=bocFinanceProductDetail&productId=YIXTT076B"
)
DEFAULT_PRODUCT_DETAIL_DB = str(DEFAULT_DB_PATH)
VIEWER_NOTE_PATH = Path(__file__).with_name("product_detail_db_viewer_note.json")
HEADERS = MOBILE_HEADERS

MOBILE_PAGE_HEADERS = {
    'User-Agent': HEADERS['User-Agent'],
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': HEADERS['Accept-Language'],
    'X-Requested-With': HEADERS['X-Requested-With'],
    'Referer': 'https://ebsnew.boc.cn/',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Dest': 'document',
}


def add_cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp


def fetch_boc(prod_code):
    """请求中银API，返回解析后的数据列表"""
    print(f"[代理] 请求产品代码: {prod_code}")
    data = post_boc_method(
        "PsnxWmpHistoryNavQueryOutlay",
        {"productId": prod_code, "subChannelId": "31", "circle": "3Y"},
        timeout=15,
        headers=HEADERS,
        uuid="177842367864015718698",
    )
    return extract_nav_list(data)


def result_or_none(response_json):
    if isinstance(response_json, dict) and response_json.get("_isException_"):
        return None
    if isinstance(response_json, dict):
        return response_json.get("result")
    return None


def load_product_detail_rows(db_path=DEFAULT_PRODUCT_DETAIL_DB):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                productId,
                productName,
                riskLevel,
                productSize_list,
                indiAmt_list,
                indiAmtRem_list,
                establishDate,
                periodTerm,
                nav_list
            FROM product_details
            ORDER BY fetchedAt DESC, productId ASC
            """
        ).fetchall()

    return [build_product_detail_view_row(dict(row)) for row in rows]


def load_viewer_note():
    if not VIEWER_NOTE_PATH.exists():
        return {"content": "", "left": None, "top": None}
    try:
        data = json.loads(VIEWER_NOTE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"content": "", "left": None, "top": None}
    if not isinstance(data, dict):
        return {"content": "", "left": None, "top": None}
    return {
        "content": str(data.get("content") or ""),
        "left": data.get("left") if isinstance(data.get("left"), (int, float)) else None,
        "top": data.get("top") if isinstance(data.get("top"), (int, float)) else None,
    }


def save_viewer_note(data):
    note = {
        "content": str(data.get("content") or "")[:20000],
        "left": data.get("left") if isinstance(data.get("left"), (int, float)) else None,
        "top": data.get("top") if isinstance(data.get("top"), (int, float)) else None,
    }
    VIEWER_NOTE_PATH.write_text(
        json.dumps(note, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return note


def load_product_nav_diff_rows(db_path=DEFAULT_PRODUCT_DETAIL_DB):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT productId, productName, establishDate, nav_list
            FROM product_details
            ORDER BY productName ASC, productId ASC
            """
        ).fetchall()

    product_rows = []
    all_dates = set()
    max_date = datetime.min
    for row in rows:
        nav_rows = parse_json_list(row["nav_list"])
        for nav_row in nav_rows:
            date = parse_date(nav_row.get("updateDate"))
            if date > max_date:
                max_date = date

    cutoff = max_date - timedelta(days=365) if max_date != datetime.min else datetime.min
    stats = {">30": 0, ">50": 0, ">100": 0}
    exceedances = []
    for row in rows:
        nav_rows = parse_json_list(row["nav_list"])
        diffs = {}
        previous = None
        establish_date = row["establishDate"] or ""
        for nav_row in nav_rows:
            current_date = parse_date(nav_row.get("updateDate"))
            current_nav = nav_row.get("nav")
            diff = ""
            if previous:
                try:
                    diff_value = (float(current_nav) - float(previous.get("nav"))) * 10000
                    diff = f"{diff_value:.2f}"
                except (TypeError, ValueError):
                    diff = ""
            if current_date >= cutoff and diff:
                date_text = str(nav_row.get("updateDate") or "")
                diffs[date_text] = diff
                all_dates.add(date_text)
                diff_number = float(diff)
                if diff_number > 30:
                    stats[">30"] += 1
                    exceedances.append({
                        "productId": row["productId"] or "",
                        "productName": row["productName"] or "",
                        "establishDate": establish_date,
                        "previousDate": str(previous.get("updateDate") or ""),
                        "currentDate": date_text,
                        "navDif": diff,
                        "annualizedYield": annualized_yield(current_nav, days_between(establish_date, date_text)),
                    })
                if diff_number > 50:
                    stats[">50"] += 1
                if diff_number > 100:
                    stats[">100"] += 1
            previous = nav_row
        product_rows.append({
            "productId": row["productId"] or "",
            "productName": row["productName"] or "",
            "diffs": diffs,
        })

    dates = sorted(all_dates, key=parse_date, reverse=True)
    return {
        "dates": dates,
        "products": product_rows,
        "stats": stats,
        "exceedances": exceedances,
        "startDate": dates[-1] if dates else "",
        "endDate": dates[0] if dates else "",
    }


def parse_json_list(value):
    if not value:
        return []
    try:
        rows = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(rows, list):
        return []
    rows = [row for row in rows if isinstance(row, dict)]
    return sorted(rows, key=lambda row: parse_date(row.get('updateDate')))


def parse_date(value):
    if not value:
        return datetime.min
    text = str(value).replace('/', '-')
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.min


def latest_entry(value, value_key):
    rows = parse_json_list(value)
    if not rows:
        return {'value': '', 'updateDate': ''}
    row = rows[-1]
    return {
        'value': str(row.get(value_key) or ''),
        'updateDate': str(row.get('updateDate') or ''),
    }


def nav_view(value):
    rows = parse_json_list(value)
    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) > 1 else {}
    latest_nav = str(latest.get('nav') or '')
    previous_nav = str(previous.get('nav') or '')
    nav_dif = ''
    try:
        nav_dif = f"{(float(latest_nav) - float(previous_nav)) * 10000:.2f}"
    except (TypeError, ValueError):
        pass
    return {
        'nav': latest_nav,
        'navDate': str(latest.get('updateDate') or ''),
        'navDif': nav_dif,
    }


def days_between(start, end):
    start_date = parse_date(start)
    end_date = parse_date(end)
    if start_date == datetime.min or end_date == datetime.min:
        return ''
    return str(max(0, (end_date - start_date).days) + 1)


def annualized_yield(nav, establish_days):
    try:
        days = float(establish_days)
        if days <= 0:
            return ''
        return f"{(float(nav) - 1) * 100 / days * 365:.2f}%"
    except (TypeError, ValueError):
        return ''


def build_product_detail_view_row(row):
    nav = nav_view(row.get('nav_list'))
    product_size = latest_entry(row.get('productSize_list'), 'productSize')
    indi_amt = latest_entry(row.get('indiAmt_list'), 'indiAmt')
    indi_amt_rem = latest_entry(row.get('indiAmtRem_list'), 'indiAmtRem')
    establish_days = days_between(row.get('establishDate'), nav['navDate'])
    return {
        'productId': row.get('productId') or '',
        'productName': row.get('productName') or '',
        'nav': nav['nav'],
        'navDate': nav['navDate'],
        'navDif': nav['navDif'],
        'productSize': product_size['value'],
        'productSizeDate': product_size['updateDate'],
        'indiAmt': indi_amt['value'],
        'indiAmtDate': indi_amt['updateDate'],
        'indiAmtRem': indi_amt_rem['value'],
        'indiAmtRemDate': indi_amt_rem['updateDate'],
        'establishDate': row.get('establishDate') or '',
        'establishDays': establish_days,
        'annualizedYield': annualized_yield(nav['nav'], establish_days),
        'periodTerm': row.get('periodTerm') or '',
        'riskLevel': row.get('riskLevel') or '',
    }


def fetch_product_detail_bundle(product_id, sub_channel_id="31"):
    product_id = product_id.strip().upper()
    base_params = {"productId": product_id, "subChannelId": sub_channel_id}

    detail_response = post_boc_method(
        "PsnxWmpProductDetailQueryOutlay",
        {**base_params, "isNewVersion": "Y"},
    )
    summary_response = post_boc_method("PsnxWmpProductSummaryQueryOutlay", base_params)
    nav_response = post_boc_method(
        "PsnxWmpHistoryNavQueryOutlay",
        {**base_params, "circle": "3Y"},
    )

    detail = result_or_none(detail_response)
    summary = result_or_none(summary_response)
    nav_result = result_or_none(nav_response)
    nav_list = nav_result.get("list", []) if isinstance(nav_result, dict) else []

    return {
        "productId": product_id,
        "subChannelId": sub_channel_id,
        "detail": detail,
        "summary": summary,
        "navList": nav_list,
        "responses": {
            "detail": detail_response,
            "summary": summary_response,
            "nav": nav_response,
        },
    }


def fetch_detail_page(url=DEFAULT_DETAIL_URL):
    """使用手机端请求头获取中银理财详情页 HTML。"""
    resp = requests.get(url, headers=MOBILE_PAGE_HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or 'utf-8'
    return resp


@app.route('/nav', methods=['GET', 'OPTIONS'])
def nav():
    if request.method == 'OPTIONS':
        return add_cors(make_response()), 200
    code = request.args.get('code', '').strip().upper()
    if not code:
        return jsonify({'success': False, 'error': '缺少产品代码'}), 400
    try:
        nav_list = fetch_boc(code)
        print(f"[代理] 成功获取 {len(nav_list)} 条记录")
        return add_cors(jsonify({'success': True, 'data': nav_list}))
    except Exception as e:
        print(f"[代理] 失败: {e}")
        return add_cors(jsonify({'success': False, 'error': str(e)})), 500


@app.route('/detail-page', methods=['GET', 'OPTIONS'])
def detail_page():
    if request.method == 'OPTIONS':
        return add_cors(make_response()), 200
    url = request.args.get('url', DEFAULT_DETAIL_URL).strip() or DEFAULT_DETAIL_URL
    try:
        upstream = fetch_detail_page(url)
        print(f"[详情页] HTTP状态码: {upstream.status_code}, 长度: {len(upstream.content)}")
        resp = make_response(upstream.text)
        resp.headers['Content-Type'] = 'text/html; charset=utf-8'
        return add_cors(resp)
    except Exception as e:
        print(f"[详情页] 失败: {e}")
        return add_cors(jsonify({'success': False, 'error': str(e)})), 500


@app.route('/product-detail', methods=['GET', 'OPTIONS'])
def product_detail():
    if request.method == 'OPTIONS':
        return add_cors(make_response()), 200
    code = request.args.get('code', 'WFXYJXRK06A').strip().upper()
    sub_channel_id = request.args.get('subChannelId', '31').strip() or '31'
    if not code:
        return add_cors(jsonify({'success': False, 'error': '缺少产品代码'})), 400
    try:
        bundle = fetch_product_detail_bundle(code, sub_channel_id=sub_channel_id)
        print(
            f"[详情聚合] 产品 {code}, detail={bool(bundle['detail'])}, "
            f"summary={bool(bundle['summary'])}, nav={len(bundle['navList'])}"
        )
        return add_cors(jsonify({'success': True, **bundle}))
    except Exception as e:
        print(f"[详情聚合] 失败: {e}")
        return add_cors(jsonify({'success': False, 'error': str(e)})), 500


@app.route('/refresh', methods=['GET', 'OPTIONS'])
def refresh():
    if request.method == 'OPTIONS':
        return add_cors(make_response()), 200
    code = request.args.get('code', '').strip().upper()
    if not code:
        return add_cors(jsonify({'success': False, 'error': '缺少产品代码'})), 400
    try:
        response_json, nav_list, embedded_data = refresh_html_data(
            product_id=code,
            html_path=DEFAULT_HTML_PATH,
            cookie=DEFAULT_COOKIE,
            timeout=20,
            print_response=True,
        )
        print(f"[刷新] 已更新 {DEFAULT_HTML_PATH}，产品 {code}，记录 {len(nav_list)} 条")
        return add_cors(jsonify({
            'success': True,
            'data': nav_list,
            'embedded': embedded_data,
            'response': response_json,
        }))
    except Exception as e:
        print(f"[刷新] 失败: {e}")
        return add_cors(jsonify({'success': False, 'error': str(e)})), 500


@app.route('/')
def index():
    return '''<h3>中银理财API代理正在运行</h3>
<p>用法：<code>http://127.0.0.1:8080/nav?code=WFZQQQPZRKA</code></p>
<p>在网页中输入产品代码点击查询即可自动调用此代理。</p>'''


@app.route('/preview-detail')
def preview_detail():
    return send_file(
        os.path.join(os.path.dirname(__file__), 'product_detail_preview.html'),
        mimetype='text/html; charset=utf-8',
    )


@app.route('/nav-chart')
def nav_chart():
    return send_file(
        os.path.join(os.path.dirname(__file__), 'nav_annualized_chart.html'),
        mimetype='text/html; charset=utf-8',
    )


@app.route('/db-viewer')
def db_viewer():
    return send_file(
        os.path.join(os.path.dirname(__file__), 'product_detail_db_viewer.html'),
        mimetype='text/html; charset=utf-8',
    )


@app.route('/db-product-details', methods=['GET', 'OPTIONS'])
def db_product_details():
    if request.method == 'OPTIONS':
        return add_cors(make_response()), 200
    try:
        products = load_product_detail_rows()
        return add_cors(jsonify({
            'success': True,
            'database': DEFAULT_PRODUCT_DETAIL_DB,
            'count': len(products),
            'products': products,
        }))
    except Exception as e:
        print(f"[数据库查看] 失败: {e}")
        return add_cors(jsonify({'success': False, 'error': str(e)})), 500


@app.route('/db-product-nav-diffs', methods=['GET', 'OPTIONS'])
def db_product_nav_diffs():
    if request.method == 'OPTIONS':
        return add_cors(make_response()), 200
    try:
        data = load_product_nav_diff_rows()
        return add_cors(jsonify({
            'success': True,
            'database': DEFAULT_PRODUCT_DETAIL_DB,
            **data,
        }))
    except Exception as e:
        print(f"[近一年净值变化] 失败: {e}")
        return add_cors(jsonify({'success': False, 'error': str(e)})), 500


@app.route('/db-viewer-note', methods=['GET', 'POST', 'OPTIONS'])
def db_viewer_note():
    if request.method == 'OPTIONS':
        return add_cors(make_response()), 200
    try:
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            note = save_viewer_note(data)
        else:
            note = load_viewer_note()
        return add_cors(jsonify({
            'success': True,
            **note,
        }))
    except Exception as e:
        print(f"[数据库查看器笔记] 失败: {e}")
        return add_cors(jsonify({'success': False, 'error': str(e)})), 500


if __name__ == '__main__':
    print(f"代理服务器运行在 http://127.0.0.1:{PORT}")
    print(f"测试: http://127.0.0.1:{PORT}/nav?code=WFZQQQPZRKA")
    print(f"详情页: http://127.0.0.1:{PORT}/detail-page")
    print(f"产品详情聚合: http://127.0.0.1:{PORT}/product-detail?code=WFXYJXRK06A")
    # html
    print(f"桌面预览页: http://127.0.0.1:{PORT}/preview-detail")
    print(f"年化净值图: http://127.0.0.1:{PORT}/nav-chart")
    print(f"数据库查看器: http://127.0.0.1:{PORT}/db-viewer")
    app.run(host='127.0.0.1', port=PORT, debug=False)
