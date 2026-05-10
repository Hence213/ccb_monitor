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

from flask import Flask, request, jsonify, make_response
import requests
import json

app = Flask(__name__)
PORT = 8082
BOC_URL = "https://ebsnew.boc.cn/BMPS/_bfwajax.do?rnd=7911&_locale=zh_CN"

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
    body = "json=" + requests.utils.quote(json.dumps(payload, ensure_ascii=False))
    print(f"[代理] 请求产品代码: {prod_code}")
    resp = requests.post(BOC_URL, data=body, headers=HEADERS, timeout=15, verify=True)
    print(f"[代理] HTTP状态码: {resp.status_code}")
    print(f"[代理] 响应前500字: {resp.text[:500]}")
    data = resp.json()
    # 实际格式: {"result": {"list": [...]}}
    if data and 'result' in data and 'list' in data['result']:
        return data['result']['list']
    if data and 'response' in data and 'data' in data['response']:
        return data['response']['data'].get('navList', [])
    return []


@app.route('/nav', methods=['GET', 'OPTIONS'])
def nav():
    if request.method == 'OPTIONS':
        resp = make_response()
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp, 200
    code = request.args.get('code', '').strip().upper()
    if not code:
        return jsonify({'success': False, 'error': '缺少产品代码'}), 400
    try:
        nav_list = fetch_boc(code)
        print(f"[代理] 成功获取 {len(nav_list)} 条记录")
        resp = jsonify({'success': True, 'data': nav_list})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        print(f"[代理] 失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/')
def index():
    return '''<h3>中银理财API代理正在运行</h3>
<p>用法：<code>http://127.0.0.1:8080/nav?code=WFZQQQPZRKA</code></p>
<p>在网页中输入产品代码点击查询即可自动调用此代理。</p>'''


if __name__ == '__main__':
    print(f"代理服务器运行在 http://127.0.0.1:{PORT}")
    print(f"测试: http://127.0.0.1:{PORT}/nav?code=WFZQQQPZRKA")
    app.run(host='127.0.0.1', port=PORT, debug=False)
