import requests
from bs4 import BeautifulSoup
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

URL_NAV = "https://www.bocwm.cn/webApi/cms/productNetWorth/getNetWorthImageByCode?productCode={}&dayCount=30"

def get_html_text(BASE_URL, product_id, product_name):
    url = BASE_URL.format(product_id)
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
    except Exception as e:
        print(f"⚠️ 请求或解析出错（{product_name}）: {e}")
        return None

def get_json_text(url, payload, headers):
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()  # 检查 HTTP 错误
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败:", e)
    except ValueError:
        print(f"⚠️ 响应不是有效的 JSON 格式")