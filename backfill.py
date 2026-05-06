# backfill.py
# 用法：python backfill.py 2026-05-05 2026-05-05

import time
import os
import sys
from datetime import datetime, timedelta

# 把 fetch_taifex 的三個函式 import 進來
from fetch_taifex import fetch_futures, fetch_options, fetch_pc_ratio
import fetch_taifex as ft

def backfill(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end   = datetime.strptime(end_str,   "%Y-%m-%d")

    os.makedirs(ft.DATA_DIR, exist_ok=True)

    current = start
    while current <= end:
        # 跳過週末
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        # 覆寫模組全域日期變數
        query_date = current.strftime("%Y-%m-%d")
        label_date = current.strftime("%Y/%m/%d")

        print(f"\n{'='*40}")
        print(f"抓取：{label_date}")
        print(f"{'='*40}")

        fetch_futures(query_date, label_date)
        fetch_options(query_date, label_date)
        fetch_pc_ratio(query_date, label_date)

        current += timedelta(days=1)
        time.sleep(2)  # 加在這裡，每天抓完等 2 秒再抓下一天

    print("\n\n✓ 補齊完成")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法：python backfill.py 開始日期 結束日期")
        print("範例：python backfill.py 2026-01-01 2026-05-05")
        sys.exit(1)

    backfill(sys.argv[1], sys.argv[2])