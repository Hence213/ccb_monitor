from request_url import get_json_text
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
RRODUCTS = [
    "稳富信用精选日开",
    "稳富信用精选7天",
    "稳富信用精选14天",
    "稳富信用精选30天",
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
    "pageSize": 10
}

def get_productcode(response_json):
    products = []
    for item in response_json['data']['rows']:
        product_name = item['productName']
        product_id = item['productCode']  # 使用    productCode 作为 ID
        products.append({
            'product_name': product_name,
            'product_id': product_id
        })

    # 打印结果
    for p in products:
        print(f"产品名称: {p['product_name']}, 产品ID: {p['product_id']}")
# 发送 POST 请求
if __name__ == "__main__":
    for product in RRODUCTS:
        PAYLOAD["productName"] = product
        response_json = get_json_text(url, PAYLOAD, HEADERS)
        if response_json:
            get_productcode(response_json)
            print(f"✅ 成功获取 {product} 的数据:")
        else:
            print(f"❌ 获取 {product} 的数据失败")