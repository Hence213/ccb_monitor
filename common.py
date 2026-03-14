
import csv
def save_to_cvs(CSV_FILE, history_data):
    max_len_data = max(history_data.values(), key=len)# 找出最长的数据列表
        # 倒序：最新日期在前
    max_len_data_reversed = list(reversed(max_len_data))
    all_dates = [dat['date'] for dat in max_len_data_reversed]

    with open(CSV_FILE, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
            # header 使用倒序日期
        header = ['产品名称'] + all_dates
        writer.writerow(header)
        for product_name, nav_list in history_data.items():
                # 转为字典便于查找
            nav_dict = {item['date']: item['nav'] for item in nav_list}
                # 按倒序的 all_dates 顺序取值
            nav_list = [nav_dict.get(date, '1') for date in all_dates]  # 没有数据的日期填 '1'
                # 计算差值
            nav_diffs = [round((float(nav_list[i]) - float(nav_list[i+1])) * 10000, 2) for i in range(0, len(nav_list) - 1)]
            row = [product_name] + nav_list[0:1] + nav_diffs
            writer.writerow(row)