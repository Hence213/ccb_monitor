"""
BOC 净值两日对比分析脚本
用法: python compare_nav.py <旧日期CSV> <新日期CSV> <code_col1> <code_col2> [output_path]
例: python compare_nav.py boc_0422.csv boc_0423.csv 产品代码 产品编码
"""
import csv, re, sys, os

def cn_to_int(cn):
    mapping = {'零':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,
               '六':6,'七':7,'八':8,'九':9,'十':10}
    return mapping.get(cn)

def parse_cn_num(s):
    if s == '十':
        return 10
    if len(s) == 2 and s[1] == '十':
        t = cn_to_int(s[0])
        return (t or 0) * 10
    if len(s) == 2 and s[0] == '十':
        t = cn_to_int(s[1])
        return 10 + (t or 0)
    return cn_to_int(s)

def should_remove(name):
    # 天（阿拉伯）
    m = re.search(r'(\d+)\s*天', name)
    if m and int(m.group(1)) > 30:
        return True
    # 天（中文）
    m = re.search(r'([零一二三四五六七八九十百]+)\s*天', name)
    if m:
        val = parse_cn_num(m.group(1).replace('百', ''))
        if val and val > 30:
            return True
    # 月（阿拉伯，>=2删）
    m = re.search(r'(\d+)\s*个月', name)
    if m and int(m.group(1)) >= 2:
        return True
    # 月（中文，一/两/零 保留）
    m = re.search(r'([零一二三四五六七八九十]+)\s*个月', name)
    if m and m.group(1) not in ('一', '两', '零'):
        return True
    # 年（任何）
    if re.search(r'(\d+)\s*年', name):
        return True
    if re.search(r'([零一二三四五六七八九十]+)\s*年', name):
        return True
    # 周期关键词
    if re.search(r'季季开|季添利|年年开|半年开|半年购|双周开|季度|六个月', name):
        return True
    return False

def read_csv(path, code_col):
    data = {}
    with open(path, encoding='gbk') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row[code_col].strip()
            data[code] = row
    return data

def to_wan(val):
    try:
        return f'{float(val) / 10000:.2f}'
    except:
        return val

def main():
    if len(sys.argv) < 5:
        print("用法: python compare_nav.py <旧日期CSV> <新日期CSV> <code_col1> <code_col2> [output_path]")
        sys.exit(1)

    path_old = sys.argv[1]
    path_new = sys.argv[2]
    col_old  = sys.argv[3]
    col_new  = sys.argv[4]
    out_path = sys.argv[5] if len(sys.argv) > 5 else 'boc_merged_nav_diff.csv'

    data_old = read_csv(path_old, col_old)
    data_new = read_csv(path_new, col_new)

    common = set(data_old.keys()) & set(data_new.keys())

    output = []
    removed = []
    for code in sorted(common):
        r_old = data_old[code]
        r_new = data_new[code]
        name  = r_new['产品名称'].strip()

        if should_remove(name):
            removed.append(name)
            continue

        nav_old = r_old['最新单位净值'].strip()
        nav_new = r_new['最新单位净值'].strip()
        try:
            diff = (float(nav_new) - float(nav_old)) * 10000
            diff_str = f'{diff:.2f}'
        except:
            diff_str = 'N/A'

        output.append({
            '产品名称': name,
            '产品代码': code,
            '产品规模（万元）': to_wan(r_new['产品规模（元）'].strip()),
            '最新单位净值(新)': nav_new,
            '最新单位净值(旧)': nav_old,
            '净值差(×10000)': diff_str,
            '个人认购总额度（万元）': to_wan(r_new['个人认购总额度（元）'].strip()),
            '个人剩余额度（万元）': to_wan(r_new['个人剩余额度（元）'].strip()),
        })

    fields = ['产品名称','产品代码','产品规模（万元）','最新单位净值(新)','最新单位净值(旧)','净值差(×10000)','个人认购总额度（万元）','个人剩余额度（万元）']
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)

    print(f'保留: {len(output)} 条，剔除: {len(removed)} 条')
    print(f'已保存: {os.path.abspath(out_path)}')
    print()
    print('--- 剔除示例（前10条）---')
    for n in removed[:10]:
        print(' ', n)

if __name__ == '__main__':
    main()
