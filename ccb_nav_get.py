from common.process_csv import save_to_cvs,sort_csv
from products.ccb import PRODUCTS
import re
from time import sleep
import re
from common.request_url import get_html_text
# 产品ID与名称的映射列表

CSV_FILE = "data/ccb_nav_history.csv"
BASE_URL = "https://www.wealthccb.com/product/{}.html"

def extract_history_nav_with_bs4(soup):
    script_tags = soup.find_all('script')
    
    for script in script_tags:
        if script.string and ('sData =' in script.string or 'xData =' in script.string):
            return js_to_json(script.string)
    
    return None
def js_to_json(js_code: str):
    idx = js_code.find("成立以来数据")
    js_code_filter = js_code[idx:] if idx != -1 else js_code
    js_code_no_space = js_code_filter.replace(r'\r\n', '').replace(' ', '')
    sdata_match = re.search(r'sData\s*=\s*\[\s*([\d.,\s\n\r]+?)\s*\];', js_code_no_space, re.DOTALL)
    xdata_match = re.search(r'xData\s*=\s*\[\s*([\d,\s\n\r]+?)\s*\];', js_code_no_space, re.DOTALL)
    
    if sdata_match and xdata_match:
        sdata_str = sdata_match.group(1)
        xdata_str = xdata_match.group(1)
        
        nav_values = re.findall(r'\d+\.\d+', sdata_str)
        date_values = re.findall(r'\d{8}', xdata_str)
        
        if nav_values and date_values:
            data_list = []
            for date, nav in zip(date_values, nav_values):
                formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
                data_list.append({"date": formatted_date, "nav": nav})
            return  data_list
    return None

# ===== 使用示例 =====

if __name__ == "__main__":
    history_data = {}
    PRODUCTS.sort(key=lambda x: x[1])  # 按产品名称排序，便于后续对齐
    for product_id, product_name in PRODUCTS:
        soup = None
        for i in range(10):
            soup = get_html_text(BASE_URL,product_id, product_name)
            if soup:
                break
            sleep(1)
        result = extract_history_nav_with_bs4(soup)
        if result:
            history_data[product_name] = result
            print(f"🔍 提取成功 -> {product_name} | 数据点数: {len(result)}")
        else:
            print(f"❌ 未能提取{product_name}数据")

    if not history_data:
        print("⚠️ 没有成功提取任何产品数据，跳过写入 CSV。")
    else:
        save_to_cvs(CSV_FILE, history_data)
        sort_csv(CSV_FILE)
        print(f"✅ 成功保存 NAV 历史数据到 {CSV_FILE}")