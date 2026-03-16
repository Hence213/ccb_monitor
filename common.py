
import csv
from datetime import datetime
from enum import Enum
class Bank(Enum):
    CCB = 1
    BOC = 2

def compute_nianhua(nav_list, jiange=7, is_all_day=False):
    if (not is_all_day) and ((len(nav_list) < jiange + 1) or (nav_list[jiange] == '1' and nav_list[jiange - 1] == '1')):
        return None  # 数据点不足，无法计算
    try:
        nav_start = float(nav_list[0])  # 最新的 NAV        
        if is_all_day:
            nianhua = (nav_start - 1) * (365 / (jiange + 1)) * 100
        else:
            nav_end = float(nav_list[jiange])  # jiange 天前的 NAV
            nianhua = ((nav_start - nav_end) / nav_end) * (365 / jiange) * 100
        return round(nianhua, 2)
    except (ValueError, ZeroDivisionError) as e:
        print(f"⚠️ 计算年化收益率出错: {e}")
        return None

def save_to_cvs(CSV_FILE, history_data, bank = Bank.CCB):
    max_len_data = max(history_data.values(), key=len)# 找出最长的数据列表
        # 倒序：最新日期在前
    max_len_data_reversed = list(reversed(max_len_data))
    all_dates = [dat['date'] for dat in max_len_data_reversed]

    with open(CSV_FILE, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
            # header 使用倒序日期
        header = ['产品名称'] + ['成立来年化'] + all_dates[0:3] +['近7日年化'] +['近14日年化'] + all_dates[3:]
        writer.writerow(header)
        for product_name, nav_list in history_data.items():
            # 计算产品成立以来的天数
            product_day = 0
            if nav_list:
                start_day = datetime.strptime(nav_list[0]['date'], "%Y-%m-%d")
                end_day = datetime.strptime(nav_list[-1]['date'], "%Y-%m-%d")
                product_day = (end_day - start_day).days + 1
            # 转为字典便于查找
            nav_dict = {item['date']: item['nav'] for item in nav_list}
                # 按倒序的 all_dates 顺序取值
            nav_list = [nav_dict.get(date, '1') for date in all_dates]  # 没有数据的日期填 '1'
                # 计算差值
            nav_diffs = [round((float(nav_list[i]) - float(nav_list[i+1])) * 10000, 2) for i in range(0, len(nav_list) - 1)]
            nianhua, nianhua_14, nianhua_7 = None, None, None
            if product_day >= 1:
                nianhua = str(compute_nianhua(nav_list, jiange=product_day -1, is_all_day=True)) + '%' #todo 中行数据对不上
            
            if bank == Bank.CCB:
                nianhua_14 = str(compute_nianhua(nav_list, jiange=14)) + '%'
                nianhua_7 = str(compute_nianhua(nav_list, jiange=7)) + '%'
            elif bank == Bank.BOC:
                nianhua_7 = str(compute_nianhua(nav_list, jiange=5)) + '%'
                nianhua_14 = str(compute_nianhua(nav_list, jiange=10)) + '%'

            row = [product_name] + [nianhua] + nav_diffs[0:3] + [nianhua_7] + [nianhua_14] + nav_diffs[3:]
            writer.writerow(row)