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
import random

from fetch_boc_nav import DEFAULT_COOKIE, DEFAULT_HTML_PATH, refresh_html_data

app = Flask(__name__)
PORT = int(os.environ.get('BOC_PROXY_PORT', '8082'))
BOC_URL_BASE = "https://ebsnew.boc.cn/BMPS/_bfwajax.do"
DEFAULT_DETAIL_URL = (
    "https://ebsnew.boc.cn/preview/bocphone/VueLocalCli4/bocFinanceDetail/index.html"
    "#/productDetail?functionCode=bocFinanceProductDetail&productId=YIXTT076B"
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 9; 2410DPN6CC Build/PQ3B.190801.03251327; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Mobile Safari/537.36',
    'Accept': 'application/json',
    # 不发送 Accept-Encoding，让服务器返回明文；requests 会自动处理 gzip
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'bfw-ctrl': 'json',
    'Origin': 'https://ebsnew.boc.cn',
    'X-Requested-With': 'com.android.browser',
    'Referer': 'https://ebsnew.boc.cn/preview/bocphone/VueLocalCli4/bocFinanceDetail/index.html',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
}

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


def build_boc_url():
    rnd = random.SystemRandom().randint(1000, 99999999)
    return f"{BOC_URL_BASE}?rnd={rnd}&_locale=zh_CN"


def add_cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp


def fetch_boc(prod_code):
    """请求中银API，返回解析后的数据列表"""
    payload = {
        "header": {
            "agent": "X-ANDR", "version": "3.1.9", "device": "android",
            "platform": "android", "plugins": "5", "page": "6",
            "local": "zh_CN", "uuid": "177842367864015718698",
            "ext": "8", "cipherType": "0", "appSequence": ""
        },
        "method": "PsnxWmpHistoryNavQueryOutlay",
        "params": {"productId": prod_code, "subChannelId": "31", "circle": "3Y"}
    }
    body = "json=" + requests.utils.quote(json.dumps(payload, ensure_ascii=False)) # type: ignore
    print(f"[代理] 请求产品代码: {prod_code}")
    resp = requests.post(build_boc_url(), data=body, headers=HEADERS, timeout=15, verify=True)
    print(f"[代理] HTTP状态码: {resp.status_code}")
    data = resp.json()
    # 实际格式: {"result": {"list": [...]}}
    if data and 'result' in data and 'list' in data['result']:
        return data['result']['list']
    if data and 'response' in data and 'data' in data['response']:
        return data['response']['data'].get('navList', [])
    return []


def build_mobile_payload(method, params):
    return {
        "header": {
            "agent": "X-ANDR", "version": "3.1.9", "device": "android",
            "platform": "android", "plugins": "5", "page": "6",
            "local": "zh_CN", "uuid": "177842367864015718698",
            "ext": "8", "cipherType": "0", "appSequence": ""
        },
        "method": method,
        "params": params,
    }


def post_boc_method(method, params, timeout=20):
    payload = build_mobile_payload(method, params)
    resp = requests.post(
        build_boc_url(),
        headers=HEADERS,
        data={"json": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def result_or_none(response_json):
    if isinstance(response_json, dict) and response_json.get("_isException_"):
        return None
    if isinstance(response_json, dict):
        return response_json.get("result")
    return None


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


if __name__ == '__main__':
    print(f"代理服务器运行在 http://127.0.0.1:{PORT}")
    print(f"测试: http://127.0.0.1:{PORT}/nav?code=WFZQQQPZRKA")
    print(f"详情页: http://127.0.0.1:{PORT}/detail-page")
    print(f"产品详情聚合: http://127.0.0.1:{PORT}/product-detail?code=WFXYJXRK06A")
    print(f"桌面预览页: http://127.0.0.1:{PORT}/preview-detail")
    app.run(host='127.0.0.1', port=PORT, debug=False)
