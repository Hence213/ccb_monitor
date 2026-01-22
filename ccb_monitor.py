import requests
import re
import csv
import os
from bs4 import BeautifulSoup
from collections import defaultdict

# 产品ID与名称的映射列表
PRODUCTS = [
    (11372340, "日开45a"),
    (10638258, "日开44a"),
    (10903623, "日开40a"),
    (10723694, "日开64a"),
    (11228000, "7天24a"),
    (11255435, "7天18专享"),
    (10996348, "7天21a"),
    (10812787, "14天21a"),
    (11158964, "14天19专享"),
    (11091037, "21天14a"),
    (11372337, "30天26a"),
    (10723698, "日申月赎27日到账"),
    (10638260, "日申月赎20日到账"),
    (10549516, "日申月赎2日到账"),
]

BASE_URL = "https://www.wealthccb.com/product/{}.html"
CSV_FILE = "data/ccb_nav_history.csv"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def extract_nav_with_bs4(html_text):
    soup = BeautifulSoup(html_text, 'html.parser')
    li_list = soup.select('li.float-left')
    for li in li_list:
        first_p = li.find('p', class_='firtst')  # 注意 typo
        second_p = li.find('p', class_='second')
        if first_p and second_p:
            text = second_p.get_text(strip=True)
            if text.startswith('最新净值(') and text.endswith(')'):
                date_str = text[5:-1]
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_str):
                    nav_str = first_p.get_text(strip=True)
                    try:
                        nav = float(nav_str)
                        return nav, date_str
                    except ValueError:
                        continue
    return None, None

def save_to_csv(product_name, nav, nav_date):
    file_exists = os.path.isfile(CSV_FILE)
    existing_records = set()

    if file_exists:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_records.add((row['产品名称'], row['净值日期']))

    if nav is not None and (product_name, nav_date) not in existing_records:
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['产品名称', '净值日期', '最新净值'])
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                '产品名称': product_name,
                '净值日期': nav_date,
                '最新净值': nav
            })
        print(f"✅ 已保存：{product_name} | {nav_date} -> {nav}")
    else:
        if nav is not None:
            print(f"ℹ️ 记录已存在（{product_name}, {nav_date}），跳过")

def fetch_product_nav(product_id, product_name):
    url = BASE_URL.format(product_id)
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        nav, nav_date = extract_nav_with_bs4(response.text)
        if nav and nav_date:
            print(f"🔍 提取成功 -> {product_name} | 净值: {nav}, 日期: {nav_date}")
        else:
            print(f"❌ 未提取到净值信息：{product_name} ({url})")
            nav, nav_date = None, None
    except Exception as e:
        print(f"⚠️ 请求或解析出错（{product_name}）: {e}")
        nav, nav_date = None, None
    save_to_csv(product_name, nav, nav_date)

def main():
    print("🔄 开始采集最新净值数据...")
    for product_id, product_name in PRODUCTS:
        fetch_product_nav(product_id, product_name)


if __name__ == "__main__":
    main()