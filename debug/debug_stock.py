# debug_stock2.py

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.twse.com.tw",
}

session = requests.Session()
session.headers.update(HEADERS)

DATE = "20260505"

# 測試幾個可能有合計的端點
urls = [
    {
        "label": "三大法人合計 FMTQIK",
        "url": f"https://www.twse.com.tw/rwd/zh/fund/FMTQIK?date={DATE}&response=json"
    },
    {
        "label": "三大法人買賣超彙總 BFI82U",
        "url": f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?date={DATE}&response=json"
    },
    {
        "label": "三大法人 T86 selectType=ALLBUT0999",
        "url": f"https://www.twse.com.tw/rwd/zh/fund/T86?date={DATE}&selectType=ALLBUT0999&response=json"
    },
]

for case in urls:
    print(f"\n測試：{case['label']}")
    try:
        r = session.get(case["url"], timeout=15)
        print(f"  Status: {r.status_code}")
        data = r.json()
        print(f"  欄位：{data.get('fields')}")
        print(f"  總筆數：{data.get('total')}")
        rows = data.get('data', [])
        print(f"  資料筆數：{len(rows)}")
        for row in rows[:3]:
            print(f"  {row}")
        # 找合計列
        for row in rows:
            if any('合計' in str(v) for v in row):
                print(f"  ★ 合計列：{row}")
    except Exception as e:
        print(f"  錯誤: {e}")