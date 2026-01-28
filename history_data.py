from datetime import date
import re
from bs4 import BeautifulSoup
from ccb_monitor import BASE_URL, get_html_text
from products import PRODUCTS,CSV_FILE
import re

def extract_history_nav_with_bs4(html_text):
    soup = BeautifulSoup(html_text, 'html.parser')
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
import csv
if __name__ == "__main__":
    history_data = {}
    for product_id, product_name in PRODUCTS:
        html_text = get_html_text(product_id, product_name)
        result = extract_history_nav_with_bs4(html_text)
        if result:
            history_data[product_name] = result
            print(f"🔍 提取成功 -> {product_name} | 数据点数: {len(result)}")
        else:
            print(f"❌ 未能提取{product_name}数据")

    if not history_data:
        print("⚠️ 没有成功提取任何产品数据，跳过写入 CSV。")
    else:
        # 找出最长的数据列表
        max_len_data = max(history_data.values(), key=len)
        # 倒序：最新日期在前
        max_len_data_reversed = list(reversed(max_len_data))
        all_dates = [dat['date'] for dat in max_len_data_reversed]

        with open(CSV_FILE, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            # header 使用倒序日期
            header = ['产品名称'] + all_dates
            writer.writerow(header)

            # 构建日期到索引的映射（用于对齐）
            date_set = set(all_dates)  # 可选，用于快速判断

            for product_name, nav_list in history_data.items():
                # 转为字典便于查找
                nav_dict = {item['date']: item['nav'] for item in nav_list}
                # 按倒序的 all_dates 顺序取值
                row = [product_name] + [nav_dict.get(date, 'null') for date in all_dates]
                writer.writerow(row)