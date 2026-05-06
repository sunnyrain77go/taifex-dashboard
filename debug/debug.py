# 建一個新檔 debug.py，貼入以下內容執行

import requests
from io import StringIO
import pandas as pd

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.taifex.com.tw/cht/3/futContractsDate",
}

session = requests.Session()
session.headers.update(HEADERS)

# Step 1：先 GET 取 cookie
print("Step 1: GET 首頁...")
r0 = session.get("https://www.taifex.com.tw/cht/3/futContractsDate", timeout=15)
print(f"  Status: {r0.status_code}")
print(f"  Cookies: {dict(session.cookies)}")

# Step 2：POST 查詢
print("\nStep 2: POST 查詢...")
r1 = session.post(
    "https://www.taifex.com.tw/cht/3/futContractsDate",
    data={
        "queryType":    "2",
        "marketCode":   "0",
        "dateaddcnt":   "",
        "queryDate":    "2026/05/02",
        "commodity_id": "TXF",
        "marketCode_back": "0",
        "commodity_id_back": "TXF"
    },
    timeout=30
)
print(f"  Status: {r1.status_code}")
print(f"  Content-Type: {r1.headers.get('Content-Type')}")
print(f"  Response 前500字：\n{r1.text[:500]}")

# Step 3：嘗試解析表格
print("\nStep 3: 解析表格...")
try:
    tables = pd.read_html(StringIO(r1.text))
    print(f"  找到 {len(tables)} 個表格")
    for i, t in enumerate(tables):
        print(f"  表格{i} shape={t.shape}, 欄位={list(t.columns)[:5]}")
        print(t.head(3).to_string())
        print()
except Exception as e:
    print(f"  解析失敗: {e}")