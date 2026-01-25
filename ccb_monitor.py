import requests
import re
import csv
import os
from bs4 import BeautifulSoup
from collections import defaultdict
from history_data import extract_history_nav_with_bs4

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
def chack_products() -> bool:
    file_exists = os.path.isfile(CSV_FILE)
    existing_products = set()

    if file_exists:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            next(f)  # 跳过标题行
            for line in f:
                product = line.split(',')[0]
                existing_products.add(product)
            if len(existing_products) == len(PRODUCTS):
                return True 
    return False

def check_date_exist(date_str) -> bool:
    file_exists = os.path.isfile(CSV_FILE)
    existing_records = set()

    if file_exists:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            existing_records = set(first_line.strip().split(','))
            if date_str in existing_records:
                return True 
    return False
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
                if check_date_exist(date_str) and chack_products():
                    print(f"ℹ️ 日期 {date_str} 已存在，跳过提取") 
                    exit(0)
                if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_str):
                    nav_str = first_p.get_text(strip=True)
                    try:
                        nav = float(nav_str)
                        return nav, date_str
                    except ValueError:
                        continue
    return None, None
def update_new_data(nav_date, nav_dict):
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
        # 获取所有产品名称（跳过标题行）
        existing_products = [row[0] for row in rows[1:]]
        if nav_date not in rows[0]:
            rows[0].insert(1, nav_date)
            # 为每一行追加对应的新数据；如果某产品没有新数据，则补空字符串（根据需求可调整）
            for i in range(1, len(rows)):
                product = rows[i][0]
                rows[i].insert(1, nav_dict.get(product, "null"))
            # 检查nav_dict中是否有新产品需要添加
        for key in nav_dict:
            if key not in existing_products:
                new_row = [key] + [nav_dict[key]] + ["null"] * (len(rows[0]) - 2) 
                rows.append(new_row)
    with open(CSV_FILE, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
def save_to_csv(nav_date, nav_list):
    file_exists = os.path.isfile(CSV_FILE)
    if file_exists:
        # 读取原始 CSV 内容
        update_new_data(nav_date, dict(nav_list))
    else:
        # 创建新 CSV 文件并写入标题和数据
        with open(CSV_FILE, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            header = ['产品名称', nav_date]
            writer.writerow(header)
            for product_name, nav in nav_list.items():
                writer.writerow([product_name, nav])

    

def fetch_product_nav(product_id, product_name):
    url = BASE_URL.format(product_id)
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        # data = extract_history_nav_with_bs4(response.text)
        nav, nav_date = extract_nav_with_bs4(response.text)
        if nav and nav_date:
            print(f"🔍 提取成功 -> {product_name} | 净值: {nav}, 日期: {nav_date}")
        else:
            print(f"❌ 未提取到净值信息：{product_name} ({url})")
            nav, nav_date = None, None
        return nav, nav_date
    except Exception as e:
        print(f"⚠️ 请求或解析出错（{product_name}）: {e}")
        return None, None


def main():
    print("🔄 开始采集最新净值数据...")
    res = defaultdict(dict)
    nav, nav_date = None, None
    for product_id, product_name in PRODUCTS:
        nav, nav_date = fetch_product_nav(product_id, product_name)
        if nav and nav_date:
            res[nav_date][product_name] = nav
    if len(res) != 1 or len(res[nav_date]) != len(PRODUCTS):
        print("ℹ️ 日期不一致，程序结束。")
        return
    save_to_csv(nav_date, res[nav_date])


if __name__ == "__main__":
    main()