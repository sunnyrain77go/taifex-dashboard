# debug2.py - 測試正確的 POST 參數

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
session.get("https://www.taifex.com.tw/cht/3/futContractsDate", timeout=15)

def flatten_cols(df):
    df.columns = [
        "_".join(str(x).strip() for x in col) if isinstance(col, tuple) else str(col)
        for col in df.columns
    ]
    return df

# 測試不同的日期格式和參數組合
test_cases = [
    {
        "label": "格式D：queryType=1（不分商品）",
        "payload": {
            "queryType": "1",
            "marketCode": "0",
            "dateaddcnt": "",
            "queryDate": "2026/05/04"
        }
    }
]

'''
    {
        "label": "格式A：日期用斜線，有commodity_id",
        "payload": {
            "queryType": "2",
            "marketCode": "0",
            "dateaddcnt": "",
            "queryDate": "2026/05/02",
            "commodity_id": "TXF",
        }
    },
    {
        "label": "格式B：日期用斜線，無commodity_id",
        "payload": {
            "queryType": "2",
            "marketCode": "0",
            "dateaddcnt": "",
            "queryDate": "2026/05/04",
        }
    },
    
    {
        "label": "格式C：日期用短橫線",
        "payload": {
            "queryType": "2",
            "marketCode": "0",
            "dateaddcnt": "",
            "queryDate": "2026-05-04",
            "commodity_id": "TXF",
        }
    }
'''

for case in test_cases:
    print(f"\n測試 {case['label']}")
    r = session.post(
        "https://www.taifex.com.tw/cht/3/futContractsDate",
        data=case["payload"],
        timeout=30
    )
    try:
        tables = pd.read_html(StringIO(r.text))
        t = tables[0]
        first_val = str(t.iloc[0, 0]) + " | " + str(t.iloc[0, 1] if t.shape[1] > 1 else "")
        print(f"  → shape={t.shape}, 第一格={first_val}")
        if "查無" not in str(t.values):
            #print("  ★ 有資料！印出前3列：")
            #print(t.head(3).to_string())
            print("  ★ 有資料！印出完整表格：")
            print(t.to_string())
    except Exception as e:
        print(f"  → 解析失敗: {e}")

    df = flatten_cols(tables[0])

    def extract_row(product_keyword):
        """找指定商品＋外資那列"""
        mask = df.apply(
            lambda r: r.astype(str).str.contains("外資").any() and
                      r.astype(str).str.contains(product_keyword).any(),
            axis=1
        )
        rows = df[mask]
        if rows.empty:
            print(f"  [警告] 找不到「{product_keyword}」外資列")
            return None
        return rows.iloc[0].values

    txf  = extract_row("臺股期貨")
    subtotal = extract_row("期貨 小計")
    print(f" txf: {txf}")
    print(f" subtotal: {subtotal}")

