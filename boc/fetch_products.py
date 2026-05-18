"""
中行 BOC 理财产品列表抓取脚本
支持多条件过滤，分页遍历，过滤指定关键词，保存为 CSV
"""

import urllib.request
import json
import csv
import time
import os
import sys
from datetime import datetime

# ─────────────────────────────────────────────
# 默认参数（可通过命令行覆盖）
# ─────────────────────────────────────────────
DEFAULT_URL = "https://e.boc.cn/ezcms/finance/v1/query"
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://e.boc.cn",
    "Referer": "https://e.boc.cn/ezcms/if/ifwb.html",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}

# 默认过滤条件（支持多选）
DEFAULT_FILTERS = [
    {"key": "productSurvivalStatus", "value": ["存续期内"]},
    {"key": "riskLevel", "value": ["中低风险", "低风险"]},
    {"key": "productSalesStatus", "value": ["在售"]},
    {"key":"salesTarget","value":["YNN","YNY","YYY"]},
]

# 默认排除关键词（名称含这些词的产品将被过滤掉）
DEFAULT_EXCLUDE_KEYWORDS = ["封闭", "对公专属", "机构专属",
                            "年", "365天", "12个月",
                            "180天","6个月","六个月", "6 个月",
                            # "90天","3个月","三个月", 
                            # "60天",  "二个月", "2个月","两个月",
                            "4个月","120天", 
                            "14 个月", "14个月", "420天",
                            "九个月", "9个月","270天",
                            "18个月", "540天", "十八个月",
                            "36个月",
                            "368天","370天","720天",
                            "7个月", "210天",
                            "日申季赎",
                            "稳享现金添利","怡享天天", "中银理财-乐享天天", "中银理财-惠享天天",
                            "招赢日日金","招赢日日欣","日盈象天天利","天天成长","鎏金日日薪",
                            "阳光碧乐活",
                            "美元", "欧元", "英镑", "港币", "澳元", "加元", "瑞士法郎",
                            "内测产品","工银理财鑫添益日开1号","工银理财核心优选最短持有7天","私行尊享阳光青私享41期（黄金自动触发策略）D",
                            ]

DEFAULT_ROWS_PER_PAGE = 2000
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_PATH = os.path.join(SCRIPT_DIR, "database", "boc_products.csv")

def fetch_page(url, headers, query_filters, start, rows):
    payload = json.dumps({
        "system": "dxcp",
        "ftype": "02",
        "start": start,
        "rows": rows,
        "query": query_filters,
        "sort": {},
        "count": "true"
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_products(
    url=DEFAULT_URL,
    headers=None,
    query_filters=None,
    rows=DEFAULT_ROWS_PER_PAGE,
    verbose=True
):
    """抓取全量产品列表"""
    if headers is None:
        headers = DEFAULT_HEADERS.copy()
    if query_filters is None:
        query_filters = DEFAULT_FILTERS.copy()

    if verbose:
        print("正在获取第一页...")

    data = fetch_page(url, headers, query_filters, 0, rows)
    total = data["data"]["totalNum"]
    all_products = list(data["data"]["result"])

    if verbose:
        print(f"总记录数: {total}")

    if total > rows:
        pages = (total + rows - 1) // rows
        for page in range(1, pages):
            start = page * rows
            if verbose:
                print(f"正在获取第 {page+1}/{pages} 页（start={start}）...")
            try:
                d = fetch_page(url, headers, query_filters, start, rows)
                all_products.extend(d["data"]["result"])
                time.sleep(0.3)
            except Exception as e:
                if verbose:
                    print(f"  第{page+1}页获取失败: {e}")

    return all_products


def filter_products(products, exclude_keywords=None):
    """按关键词过滤产品名称"""
    if exclude_keywords is None:
        exclude_keywords = DEFAULT_EXCLUDE_KEYWORDS

    def is_excluded(name):
        for kw in exclude_keywords:
            if kw in name:
                return True
        return False

    return [p for p in products if not is_excluded(p.get("productName", ""))]


def save_to_csv(products, output_path):
    """保存产品列表到 CSV（按产品名称升序排序）"""
    products = sorted(products, key=lambda p: p.get("productName", ""))
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["产品代码", "产品名称", "风险等级", "产品状态", "销售状态"])
        for i, p in enumerate(products, 1):
            writer.writerow([
                p.get("productCode", ""),
                p.get("productName", ""),
                p.get("riskLevel", ""),
                p.get("productSurvivalStatus", ""),
                p.get("productSalesStatus", ""),
            ])
    return output_path


def print_preview(products, n=30):
    """打印预览"""
    print(f"\n共 {len(products)} 条产品")
    print(f"{'序号':^4} {'产品代码':<25} {'风险等级':<10} {'产品名称'}")
    print("-" * 90)
    for i, p in enumerate(products[:n], 1):
        print(f"{i:^4} {p.get('productCode',''):<25} {p.get('riskLevel',''):<10} {p.get('productName','')}")
    if len(products) > n:
        print(f"\n... 还有 {len(products) - n} 条，已保存至 CSV")


def main(
    output_path=None,
    query_filters=None,
    exclude_keywords=None,
    rows=DEFAULT_ROWS_PER_PAGE,
):
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d")
        output_path = os.path.join(
            os.getcwd(),
            f"boc_products_{ts}.csv"
        )

    products = fetch_all_products(
        query_filters=query_filters,
        rows=rows,
    )

    filtered = filter_products(products, exclude_keywords)

    save_to_csv(filtered, output_path)
    print_preview(filtered)
    print(f"\n文件已保存: {output_path}")

    return output_path


if __name__ == "__main__":
    # 支持命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="中行理财产品列表抓取")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT_PATH, help="输出 CSV 路径")
    parser.add_argument("--rows", "-r", type=int, default=DEFAULT_ROWS_PER_PAGE, help="每页条数")
    parser.add_argument("--exclude", "-e", nargs="*", default=None, help="排除关键词（名称含该词则过滤）")
    args = parser.parse_args()

    main(
        output_path=args.output,
        exclude_keywords=args.exclude,
        rows=args.rows,
    )
