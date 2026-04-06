
import csv
from datetime import datetime
from enum import Enum
class Bank(Enum):
    CCB = 1
    BOC = 2
def compute_nianhua(nav_end, nav_start, day_jiange):
    try:
        nianhua = ((float(nav_end) - float(nav_start)) / float(nav_start)) * (365 / day_jiange) * 100
        return round(nianhua, 2)
    except (ValueError, ZeroDivisionError) as e:
        print(f"⚠️ 计算年化收益率出错: {e}")
        return None
# def compute_nianhua(nav_list, jiange=7, is_all_day=False,bank = Bank.CCB):
#     if (not is_all_day) and ((len(nav_list) < jiange + 1) or (nav_list[jiange] == '1' and nav_list[jiange - 1] == '1')):
#         return None  # 数据点不足，无法计算
#     try:
#         nav_start = float(nav_list[0]) if nav_list[0] != '1' else float(nav_list[1])  # 最新的 NAV 区分t+1和
#         if is_all_day:
#             nianhua = (nav_start - 1) * (365 / (jiange + 1)) * 100
#         else:
#             nav_end = float(nav_list[jiange])  # jiange 天前的 NAV
#             if bank == Bank.CCB:
#                 nianhua = ((nav_start - nav_end) / nav_end) * (365 / jiange) * 100
#             elif bank == Bank.BOC:
#                 nianhua = ((nav_start - nav_end) / nav_end) * 365 / (jiange/5*7) * 100
#         return round(nianhua, 2)
#     except (ValueError, ZeroDivisionError) as e:
#         print(f"⚠️ 计算年化收益率出错: {e}")
#         return None

# 读取 CSV
def sort_csv(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # 读取表头
        rows = list(reader)

# 按第2列（索引1）倒序排序
# 假设第二列是数字；如果是字符串，去掉 key 中的 float 转换
    try:
        rows.sort(key=lambda x: float(x[1]), reverse=True)
    except ValueError:
    # 如果无法转为数字，则按字符串排序
        rows.sort(key=lambda x: x[2], reverse=True)

# 写入新文件或打印
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

def save_to_cvs(CSV_FILE, history_data, bank = Bank.CCB,product_start_date = {}):
    max_len_data = max(history_data.values(), key=len)# 找出最长的数据列表
        # 倒序：最新日期在前
    max_len_data_reversed = list(reversed(max_len_data))
    all_dates = [dat['date'] for dat in max_len_data_reversed]

    with open(CSV_FILE, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
            # header 使用倒序日期
        header = ['产品名称'] + all_dates[0:3] + ['近7日年化'] +['近14日年化'] + ['成立来年化'] + ['最新净值']+ ['成立日期'] + ['成立天数'] + all_dates[3:] 
        writer.writerow(header)
        for product_name, nav_list in history_data.items():
            # 计算产品成立以来的天数
            start_date = ''
            product_day = 0
            if nav_list:
                if bank == Bank.CCB:
                    start_date = nav_list[0]['date']
                elif bank == Bank.BOC:
                    start_date = product_start_date.get(product_name, '')  # 如果没有提供成立日期，使用默认值
                try:
                    start_day = datetime.strptime(start_date, "%Y-%m-%d")
                    end_day = datetime.strptime(nav_list[-1]['date'], "%Y-%m-%d")
                    product_day = (end_day - start_day).days + 1
                except ValueError:
                    print(f"⚠️ 日期格式错误（{product_name}）: {start_date} 或 {nav_list[-1]['date']}")
            # 转为字典便于查找
            nav_dict = {item['date']: item['nav'] for item in nav_list}
                # 按倒序的 all_dates 顺序取值
            nav_list = [nav_dict.get(date, '1') for date in all_dates]  # 没有数据的日期填 '1'
                # 计算差值
            is_t2 = False
            if nav_list[0] == '1':
                # 剔除掉
                is_t2 = True
                nav_list = nav_list[1:]
            
            nav_diffs = [round((float(nav_list[i]) - float(nav_list[i+1])) * 10000, 2) for i in range(0, len(nav_list) - 1)]
            nianhua, nianhua_14, nianhua_7 = None, None, None
            if product_day >= 1:
                nianhua = str(compute_nianhua(nav_list[0], '1', product_day)) + '%' #todo 中行长时间的数据对不上，从产品网页获取成立日期，https://www.bocwm.cn/html/1//4/7875.html
            
            if product_day >= 7:
                if bank == Bank.CCB:
                    nianhua_7 = str(compute_nianhua(nav_list[0],nav_list[7], 7)) + '%'
                elif bank == Bank.BOC:
                    nianhua_7 = str(compute_nianhua(nav_list[0],nav_list[5], 7)) + '%'
            if product_day >= 14:
                if bank == Bank.CCB:
                    nianhua_14 = str(compute_nianhua(nav_list[0],nav_list[14], 14)) + '%'
                elif bank == Bank.BOC:
                    nianhua_14 = str(compute_nianhua(nav_list[0],nav_list[10], 14)) + '%'

            if is_t2:
                row = [product_name] + [None] + nav_diffs[0:2] + [nianhua_7] + [nianhua_14] + [nianhua] + [nav_list[0]] + [start_date] + [product_day] + nav_diffs[2:]
            else:
                row = [product_name] + nav_diffs[0:3] + [nianhua_7] + [nianhua_14] + [nianhua] + [nav_list[0]] + [start_date] + [product_day] + nav_diffs[3:]
            writer.writerow(row)
