#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_stock_net.py
每日抓取證交所三大法人現貨買賣超，append 進 data/stock_net.json

資料來源：https://www.twse.com.tw/rwd/zh/fund/BFI82U
單位：元（存檔時換算成億元）
"""

import os
import sys
from datetime import datetime, date

# 引用您的工具箱
from config import DATA_DIR
from utils import load_json, save_json, already_exists, make_session, post_and_parse, flatten_cols

# ============================================================
# 設定
# ============================================================

STOCK_NET_JSON = os.path.join(DATA_DIR, "stock_net.json")

# 日期格式：證交所用 YYYYMMDD
TODAY_TWSE  = datetime.now().strftime("%Y%m%d")   # 查詢用：20260505
TODAY_LABEL = datetime.now().strftime("%Y/%m/%d")  # 存檔用：2026/05/05

# ============================================================
# 工具函式
# ============================================================

def to_yi(val_str):
    """字串金額（元）→ 億元（保留2位小數）"""
    try:
        # 去除逗號、空格，轉成數字
        clean_val = str(val_str).replace(",", "").strip()
        return round(int(clean_val) / 1e8, 2)
    except Exception:
        return 0.0

# ============================================================
# 主函式
# ============================================================

def fetch_stock_net(twse_date=None, label_date=None):
    """
    twse_date：YYYYMMDD（給 API 用）
    label_date：YYYY/MM/DD（存 JSON 用）
    """
    q_date = twse_date or TODAY_TWSE
    l_date = label_date or TODAY_LABEL

    print("▶ 現貨三大法人買賣超")

    if already_exists(STOCK_NET_JSON, l_date):
        print(f"  今日資料已存在，跳過（{l_date}）")
        return False

    session = make_session()
    
    # 證交所 BFI82U 頁面 POST 參數
    tables = post_and_parse(session,
        url="https://www.twse.com.tw/rwd/zh/fund/BFI82U",
        payload={
            "type": "day",
            "dayDate": q_date, # 20260504
            "response": "html"
        }
    )

    if not tables:
        print("  [警告] 抓取失敗或無資料")
        return False

    # 通常第一張表就是買賣超彙總
    df = flatten_cols(tables[0])
    
    # 建立 {單位名稱: 買賣差額} 的 dict
    # 假設欄位名稱為 '單位名稱' 和 '買賣差額'
    # 證交所表格通常第一欄是單位，最後一欄是差額
    net_map = {}
    for _, row in df.iterrows():
        name = str(row.iloc[0]).strip()
        net_map[name] = to_yi(row.iloc[3]) # 買賣差額通常在第四欄 (index 3)

    if not net_map:
        print("  [警告] 無法解析資料內容")
        return False


    # 取各身份別
    foreign     = net_map.get("外資及陸資(不含外資自營商)", 0.0)
    foreign_dealer = net_map.get("外資自營商", 0.0)
    trust       = net_map.get("投信", 0.0)
    dealer_self = net_map.get("自營商(自行買賣)", 0.0)
    dealer_hedge= net_map.get("自營商(避險)", 0.0)
    dealer_total= round(dealer_self + dealer_hedge, 2)
    total       = net_map.get("合計", 0.0)

    # 外資合計（含外資自營商）
    foreign_total = round(foreign + foreign_dealer, 2)

    record = {
        "date":           l_date,
        "foreign":        foreign,        # 外資及陸資（不含外資自營商）億元 ★
        "foreign_dealer": foreign_dealer, # 外資自營商 億元
        "foreign_total":  foreign_total,  # 外資合計（含自營）億元
        "trust":          trust,          # 投信 億元
        "dealer_self":    dealer_self,    # 自營商自行買賣 億元
        "dealer_hedge":   dealer_hedge,   # 自營商避險 億元
        "dealer_total":   dealer_total,   # 自營商合計 億元
        "total":          total,          # 三大法人合計 億元
    }

    records = load_json(STOCK_NET_JSON)
    records.append(record)

    # 計算近5日外資累計（含今日）
    recent_5 = [r["foreign"] for r in records[-5:]]
    record["foreign_5d"] = round(sum(recent_5), 2)

    # 更新最後一筆（加入 foreign_5d）
    records[-1] = record
    save_json(STOCK_NET_JSON, records)

    sign = lambda v: f"+{v}" if v >= 0 else str(v)
    direction = "買超" if foreign >= 0 else "賣超"
    print(f"  ✓ 寫入成功")
    print(f"    外資現貨   = {sign(foreign)} 億元（{direction}）")
    print(f"    投信       = {sign(trust)} 億元")
    print(f"    自營商合計 = {sign(dealer_total)} 億元")
    print(f"    三大合計   = {sign(total)} 億元")
    print(f"    外資近5日  = {sign(record['foreign_5d'])} 億元")
    return True


# ============================================================
# 主程式
# ============================================================

if __name__ == "__main__":
    # 允許指定日期：python fetch_stock_net.py 2026/05/02
    if len(sys.argv) > 1:
        try:
            target = datetime.strptime(sys.argv[1], "%Y/%m/%d")
            TODAY_TWSE  = target.strftime("%Y%m%d")
            TODAY_LABEL = target.strftime("%Y/%m/%d")
            print(f"[手動指定日期] {TODAY_LABEL}")
        except ValueError:
            print("日期格式錯誤，請用 YYYY/MM/DD，例如：python fetch_stock_net.py 2026/05/02")
            sys.exit(1)

    print(f"=== 現貨買賣超抓取 {TODAY_LABEL} ===\n")

    if date.today().weekday() >= 5:
        print("今日為週末，無交易資料，結束執行。")
        sys.exit(0)

    os.makedirs(DATA_DIR, exist_ok=True)
    fetch_stock_net()
    print("\n=== 完成 ===")