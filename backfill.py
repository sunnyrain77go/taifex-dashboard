#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill.py
補抓歷史資料

用法：python backfill.py 2026-01-01 2026-05-05
"""

import sys
import time
import os
from datetime import datetime, timedelta

from fetch_taifex import fetch_futures, fetch_options, fetch_pc_ratio, fetch_oi_strike
import fetch_taifex as ft
from fetch_stock_net import fetch_stock_net


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

        query_date = current.strftime("%Y-%m-%d")   # 期交所格式
        label_date = current.strftime("%Y/%m/%d")   # JSON 存檔格式
        twse_date  = current.strftime("%Y%m%d")     # 證交所格式

        print(f"\n{'='*40}")
        print(f"抓取：{label_date}")
        print(f"{'='*40}")

        fetch_futures(query_date, label_date)
        fetch_options(query_date, label_date)
        fetch_pc_ratio(query_date, label_date)
        fetch_oi_strike(query_date, label_date)
        fetch_stock_net(twse_date, label_date)

        current += timedelta(days=1)
        time.sleep(2)   # 避免請求過快被擋

    print("\n\n✓ 補齊完成")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法：python backfill.py 開始日期 結束日期")
        print("範例：python backfill.py 2026-01-01 2026-05-05")
        sys.exit(1)

    backfill(sys.argv[1], sys.argv[2])