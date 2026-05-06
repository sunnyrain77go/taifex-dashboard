# debug3.py - 找各履約價 OI 的正確網址

import requests
from io import StringIO
import pandas as pd

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.taifex.com.tw/cht/3/futContractsDate",
}

session = requests.Session()
session.headers.update(HEADERS)
session.get("https://www.taifex.com.tw/cht/3/futContractsDate", timeout=15)

# 測試幾個可能的網址
urls = [
    {
        "label": "選擇權各履約價未平倉 A",
        "url": "https://www.taifex.com.tw/cht/3/optSelectContractsDate",
        "payload": {"queryType": "4", "queryDate": "2026-05-05", "commodity_id": "TXO"}
    },
    {
        "label": "選擇權各履約價未平倉 B",
        "url": "https://www.taifex.com.tw/cht/3/bfOpt020000",
        "payload": {"queryType": "4", "queryDate": "2026-05-05", "commodity_id": "TXO"}
    },
    {
        "label": "選擇權各履約價未平倉 C（pcRatio）",
        "url": "https://www.taifex.com.tw/cht/3/pcRatio",
        "payload": {"queryDate": "2026-05-05"}
    },
]

for case in urls:
    print(f"\n測試：{case['label']}")
    try:
        r = session.post(case["url"], data=case["payload"], timeout=15)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            tables = pd.read_html(StringIO(r.text))
            for i, t in enumerate(tables):
                print(f"  表格{i}: shape={t.shape}")
                print(f"  欄位: {list(t.columns)[:6]}")
                print(f"  前2列:\n{t.head(2).to_string()}")
    except Exception as e:
        print(f"  錯誤: {e}")