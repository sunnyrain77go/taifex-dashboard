# debug4.py

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

urls = [
    {
        "label": "各履約價未平倉 A",
        "url": "https://www.taifex.com.tw/cht/3/callsAndPutsDate",
        "payload": {"queryType": "4", "queryDate": "2026-05-05", "commodity_id": "TXO"}
    },
    {
        "label": "各履約價未平倉 B",
        "url": "https://www.taifex.com.tw/cht/3/callsAndPutsDate",
        "payload": {"queryType": "1", "queryDate": "2026-05-05", "commodity_id": "TXO"}
    },
    {
        "label": "各履約價未平倉 C",
        "url": "https://www.taifex.com.tw/cht/3/callsAndPutsDate",
        "payload": {"queryType": "2", "queryDate": "2026-05-05", "commodity_id": "TXO"}
    },
    {
        "label": "各履約價未平倉 D",
        "url": "https://www.taifex.com.tw/cht/3/callsAndPutsDate",
        "payload": {"queryType": "3", "queryDate": "2026-05-05", "commodity_id": "TXO"}
    },
]

for case in urls:
    print(f"\n測試：{case['label']} (queryType={case['payload'].get('queryType')})")
    try:
        r = session.post(case["url"], data=case["payload"], timeout=15)
        print(f"  Status: {r.status_code}")
        tables = pd.read_html(StringIO(r.text))
        for i, t in enumerate(tables):
            print(f"  表格{i}: shape={t.shape}")
            print(f"  欄位前6個: {list(t.columns)[:6]}")
            print(f"  前3列:\n{t.head(3).to_string()}")
    except Exception as e:
        print(f"  錯誤: {e}")