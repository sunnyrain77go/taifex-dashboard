# debug10.py - 確認欄位和資料結構

import requests
import pandas as pd
from io import StringIO

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.taifex.com.tw/cht/3/dlOptDailyMarketView",
}

session = requests.Session()
session.headers.update(HEADERS)
session.get("https://www.taifex.com.tw/cht/3/dlOptDailyMarketView", timeout=15)

payload = {
    "down_type":      "1",
    "commodity_id":   "TXO",
    "commodity_id2":  "",
    "queryStartDate": "2026/05/05",
    "queryEndDate":   "2026/05/05",
    "button3":        "下載",
}

r = session.post(
    "https://www.taifex.com.tw/cht/3/dlOptDataDown",
    data=payload,
    timeout=30
)

text = r.content.decode("big5")
df = pd.read_csv(StringIO(text))

# 清理欄位名稱
df.columns = df.columns.str.strip()

print("欄位列表：")
for i, c in enumerate(df.columns):
    print(f"  [{i}] {c}")

print(f"\n總列數：{len(df)}")
print(f"\n到期月份種類：{df['到期月份(週別)'].unique()}")
print(f"買賣權種類：{df['買賣權'].unique()}")
print(f"交易時段種類：{df['交易時段'].unique()}")

# 只看當月、一般時段、有未沖銷的
df['未沖銷契約數'] = pd.to_numeric(df['未沖銷契約數'], errors='coerce')
df['履約價'] = pd.to_numeric(df['履約價'], errors='coerce')

df_filtered = df[
    (df['交易時段'] == '一般') &
    (df['未沖銷契約數'].notna()) &
    (df['未沖銷契約數'] > 0)
].copy()

print(f"\n過濾後（一般時段＋有OI）：{len(df_filtered)} 列")
print(f"到期月份：{df_filtered['到期月份(週別)'].unique()}")

# 最大OI前5名
print("\n== Call OI 前5 ==")
call_df = df_filtered[df_filtered['買賣權'] == '買權'].groupby('履約價')['未沖銷契約數'].sum()
print(call_df.nlargest(5))

print("\n== Put OI 前5 ==")
put_df = df_filtered[df_filtered['買賣權'] == '賣權'].groupby('履約價')['未沖銷契約數'].sum()
print(put_df.nlargest(5))