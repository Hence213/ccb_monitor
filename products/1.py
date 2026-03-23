import pandas as pd

df1 = pd.read_csv('cob1.csv')
df2 = pd.read_csv('cob.csv')

if len(df1) != len(df2):
    print("警告：两文件行数不一致，按行合并可能导致错位！")

# 直接把 '剩余额度' 列赋值过去（要求行数一致）
df2['剩余额度'] = df1['剩余额度']

df2.to_csv('cob_updated.csv', index=False, encoding='utf-8-sig')
print("按行顺序合并完成！结果保存到 cob_updated.csv")