URL_NAV = "https://www.bocwm.cn/webApi/cms/productNetWorth/getNetWorthImageByCode?productCode={}"
# &dayCount=30
from common import Bank, save_to_cvs
from get_boc_product import HEADERS
import csv
import requests
PRODUCTS_FILE = "cob_products.csv"
NAV_FILE = "data/boc_nav_history.csv"

def get_url_nav(product_id, product_name):
    url = URL_NAV.format(product_id)
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️ 请求或解析出错（{product_name}）: {e}")
        return None
def update_nav_history():
    history_data ={'0_30天26a': [{'date': '2026-01-20', 'nav': '1.000012'}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, {...}, ...]}
    nav_data = {}
    with open(PRODUCTS_FILE, mode='r', encoding='utf-8') as file:
        # 创建 CSV 读取器
        reader = csv.DictReader(file)
        # 遍历每一行，提取 productName 字段
        for row in reader:
            product_name = row['productName']
            product_id = row['productCode']
            res = get_url_nav(product_id, product_name)
            if res and 'dateList' in res and 'shareNetWorthList' in res:
                product_data = [{"date": item, "nav": item1} for item,item1 in zip(res['dateList'], res['shareNetWorthList'])]
                nav_data[product_name] = product_data
                print(f"✅ 成功获取 {product_name} 的数据: 数据点数: {len(product_data)}")
            else:   
                print(f"❌ 解析 {product_name} 的数据失败")
        return nav_data


if __name__ == "__main__":
    nav_history = update_nav_history()
    if nav_history:
        save_to_cvs(NAV_FILE, nav_history, bank = Bank.BOC)
        print(f"✅ 成功保存 NAV 历史数据到 {NAV_FILE}")
    else:
        print("⚠️ 没有成功获取任何 NAV 数据，跳过保存 CSV。")