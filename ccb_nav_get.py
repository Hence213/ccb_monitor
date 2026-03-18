from common import save_to_cvs,sort_csv
import re
from time import sleep
import re
from request_url import get_html_text
# 产品ID与名称的映射列表
PRODUCTS = [
    ### 日开
    # (10638258, "0_日开44a"),
    # (10214651, "1_日开17a"),
    (9532835,  "按日开放第5期A"),
    (10903623, "按日开放第40期A"),
    (11372340, "按日开放第45期A"),
    (10723694, "按日开放第64期A"),
    (11557292, "按日开放第65期A"),
    (11756509, "按日开放第10期"),
    (11955168, "按日开放第41期"),
    # 七天系列
    (10297146, "7天第20期A"),
    (10996348, "7天第21期A"),
    (11228000, "7天第24期A"),
    (11557288, "7天第25期A"),
    (11464059, "7天第28期A"),
    (11570433, "日申周赎10"),
    (11570434, "日申周赎9"),
    (11570435, "日申周赎8"),
    (11464060, "日申周赎7"),
    (11464047, "日申周赎6"),
    (11756508, "7天第35期"),
    (12158446, "7天第36期"),
    # 14，21天系列
    (11091037, "21天第14期A"),
    (10812787, "14天第21期A"),

    # 30天系列
    (10549511, "30天第17期A"),
    (10723691, "30天第21期A"),
    (10297149, "30天第23期A"),
    (11372337, "30天第26期A"),
    (10903617, "30天第27期A"),
    (11995099, "30天第35期"),
    (12158447, "30天第30期"),
    
    ### 长期 or 专享 产品
    # (11255435, "2_7天18专享"),
    # (11158964, "2_14天19专享"),
    # (11636594, "2_30天34专享"),
    # (10297144, "2_60天4a"),
    # (11372334, "2_90天13a"),
    # (11649887, "2_90天6a"),
    # (11227991, "2_90天1a"),
    # (10996342, "2_180天4a睿鑫"),
    # (9750144,  "2_180天6a睿鑫"),
    # (11649884, "2_180天1a睿鑫")
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
        sort_csv(CSV_FILE)
        print(f"✅ 成功保存 NAV 历史数据到 {CSV_FILE}")