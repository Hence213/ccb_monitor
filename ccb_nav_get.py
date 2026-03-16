from common import save_to_cvs
import re
from time import sleep
import re
from request_url import get_html_text
# 产品ID与名称的映射列表
PRODUCTS = [
    ### 日开
    # (10638258, "0_日开44a"),
    # (10214651, "1_日开17a"),
    (9532835,  "1_日开5a"),
    (11756509, "0_日开10"),
    (10903623, "0_日开40a"),
    (11955168, "0_日开41"),
    (11372340, "0_日开45a"),
    (10723694, "0_日开64a"),
    (11557292, "0_日开65a"),

    # 七天系列
    (10297146, "0_7天20a"),
    (10996348, "1_7天21a"),
    (11228000, "1_7天24a"),
    (11557288, "0_7天25a"),
    (11464059, "0_7天28a"),
    (11756508, "0_7天35"),
    (11570433, "0_日申周赎10"),
    (11570434, "1_日申周赎9"),
    (11570435, "1_日申周赎8"),
    (11464060, "1_日申周赎7"),
    (11464047, "1_日申周赎6"),
    # 14，21天系列
    (11091037, "1_21天14a"),
    (10812787, "1_14天21a"),

    # 30天系列
    (10549511, "2_30天17a"),
    (10723691, "2_30天21a"),
    (10297149, "2_30天23a"),
    (11372337, "0_30天26a"),
    (10903617, "2_30天27a"),
    (11995099, "0_30天35a"),
    
    ### 长期 or 专享 产品
    (11255435, "2_7天18专享"),
    (11158964, "2_14天19专享"),
    (11636594, "2_30天34专享"),
    (10297144, "2_60天4a"),
    (11372334, "2_90天13a"),
    (11649887, "2_90天6a"),
    (11227991, "2_90天1a"),
    (10996342, "2_180天4a睿鑫"),
    (9750144,  "2_180天6a睿鑫"),
    (11649884, "2_180天1a睿鑫")
]
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