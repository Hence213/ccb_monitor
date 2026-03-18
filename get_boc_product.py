import csv

from request_url import get_post_json_text
# 请求 URL
url = "https://www.bocwm.cn/webApi/cms/product/queryStaticProducts"

# 请求头（Headers）
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Origin": "https://www.bocwm.cn",
    "Referer": "https://www.bocwm.cn/html/1//151/183/index.html",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "X-CSRF-TOKEN": "csrfToken",  # ⚠️ 注意：这个 token 可能是动态的！
    "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"'
}
EXCLUDE_PRODUCTS = [
    "稳富信用精选稳健日开",
    "短债"
]
RRODUCTS = [
    "稳富信用精选",
    "增强信用精选",
    
    "增强打新策略",
    
    "稳富全球配置",
    "增强全球配置",
    
    "稳富纯债",
    
    "行业轮动策略",
    "指数轮动策略",
]
DAYS = [
    "日开", #短债 删除
    "7天",
    "14天",
    "30天",
]

# 请求体（JSON 数据）
PAYLOAD = {
    "style": "",
    "timeLimit": "3个月及以内",
    "riskLevel": "",
    "currency": "",
    "productTypeName": "",
    "productClass": [],
    "investorRange": "个人",
    "productName": "{}",
    "pageNo": 1,
    "pageSize": 1000
}

def updat_products(response_json):
    product_names_set = set()  # 使用集合避免重复
    with open('cob_products.csv', mode='r', encoding='utf-8') as file:
        # 创建 CSV 读取器
        reader = csv.DictReader(file)
    
    # 遍历每一行，提取 productName 字段
        for row in reader:
            product_name = row['productName']
            product_names_set.add(product_name)
    new_products = []
    for item in response_json['data']['rows']:
        product_name = item['productName']
        product_id = item['productCode']  # 使用productCode 作为 ID
        if not any(day in product_name for day in DAYS):
            continue  # 如果产品名称中不包含指定的天数关键词，则跳过
        # product_name不与product_names_set中的任何名称重叠
        if product_name.startswith("中银理财-"):
            product_name = product_name[len("中银理财-"):]
        is_exist = False
        for item in product_names_set:
            if product_name in item:
                is_exist = True
                break
            # product_name去除"中银理财"前缀
        if not is_exist:
            new_products.append((product_name, product_id))

    # 将新产品添加到 CSV 文件中
    if new_products:
        sorted_new_products = sorted(new_products, key=lambda x: x[0])  # 按产品名称排序
        with open('cob_products.csv', mode='a', encoding='utf-8', newline='') as file:
            if len(product_names_set) == 0:  # 如果原文件没有任何产品，写入表头
                writer = csv.writer(file)
                writer.writerow(['productName', 'productCode'])
            writer = csv.writer(file)
            for product_name, product_id in sorted_new_products:
                if not any(exclude in product_name for exclude in EXCLUDE_PRODUCTS): # 排除包含特定关键词的产品
                    writer.writerow([product_name, product_id])

# 发送 POST 请求
if __name__ == "__main__":
    for product in RRODUCTS:
        PAYLOAD["productName"] = product
        response_json = get_post_json_text(url, PAYLOAD, HEADERS)
        if response_json:
            updat_products(response_json)
            print(f"✅ 成功获取 {product} 的数据:")
        else:
            print(f"❌ 获取 {product} 的数据失败")