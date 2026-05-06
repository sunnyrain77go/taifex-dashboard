# debug5.py

import requests
import pandas as pd
from io import StringIO

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.taifex.com.tw/cht/3/futContractsDate",
}

session = requests.Session()
session.headers.update(HEADERS)
session.get("https://www.taifex.com.tw/cht/3/futContractsDate", timeout=15)

r = session.post(
    "https://www.taifex.com.tw/cht/3/callsAndPutsDate",
    data={"queryType": "4", "queryDate": "2026-05-05", "commodity_id": "TXO"},
    timeout=30
)
r.encoding = "utf-8"

df = pd.read_html(StringIO(r.text))[0]

# 攤平 header
df.columns = [
    "_".join(str(x).strip() for x in col) if isinstance(col, tuple) else str(col)
    for col in df.columns
]

# 找外資列
mask = df.apply(lambda row: row.astype(str).str.contains("外資").any(), axis=1)
rows = df[mask]

print(f"找到 {len(rows)} 列外資資料\n")
for _, row in rows.iterrows():
    print("── 這列的每個欄位值：")
    for i, (col, val) in enumerate(zip(df.columns, row.values)):
        print(f"  [{i:02d}] {col} = {val}")
    print()