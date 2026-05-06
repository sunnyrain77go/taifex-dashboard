#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_taifex.py
每日抓取期交所三組資料，存入 data/ 資料夾的 JSON 檔

模組1：外資台指期貨淨未平倉（futContractsDate）
模組2：外資選擇權 Call/Put 未平倉 + 淨部位（callsAndPutsDate）
模組3：全市場 P/C Ratio 歷史（pcRatio）

抓取方式：POST + pandas.read_html()
日期格式：YYYY-MM-DD（期交所 POST 接受格式）
"""

import requests
import pandas as pd
import json
import os
import sys
from io import StringIO
from datetime import datetime, date

from config import DATA_DIR
from utils import load_json, save_json, already_exists, make_session, post_and_parse, flatten_cols
import options_analysis
from fetch_stock_net import fetch_stock_net, STOCK_NET_JSON

# ============================================================
# 設定（在 Colab 測試時修改這裡的日期）
# ============================================================

# 正式跑當天資料時用這兩行：
TODAY_QUERY = datetime.now().strftime("%Y-%m-%d")
TODAY_LABEL = datetime.now().strftime("%Y/%m/%d")

FUTURES_JSON = os.path.join(DATA_DIR, "futures.json")
OPTIONS_JSON = os.path.join(DATA_DIR, "options_pc.json")
PC_JSON      = os.path.join(DATA_DIR, "pc_ratio.json")

# ============================================================

# ============================================================
# 工具函式
# ============================================================

# (已搬移至 utils.py)


# (已搬移至 utils.py)


def safe_int(val):
    try:
        return int(str(val).replace(",", "").strip())
    except Exception:
        return 0


def safe_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except Exception:
        return None


# ============================================================
# 模組1：外資台指期貨淨未平倉口數
# URL: /cht/3/futContractsDate
#
# 欄位 index（攤平後共 15 欄）：
#  [0]  序號      [1] 商品名稱   [2] 身份別
#  [3]  多方交易口數              [4]  多方交易契約金額
#  [5]  空方交易口數              [6]  空方交易契約金額
#  [7]  交易淨口數                [8]  交易淨契約金額
#  [9]  多方未平倉口數            [10] 多方未平倉契約金額
#  [11] 空方未平倉口數            [12] 空方未平倉契約金額
#  [13] 淨未平倉口數 ★           [14] 淨未平倉契約金額
# ============================================================

def fetch_futures(query_date, label_date):
    print(f"▶ 模組1：期貨淨口數 (日期: {label_date}, 查詢: {query_date})")

    if already_exists(FUTURES_JSON, label_date):
        print(f"  今日資料已存在，跳過（{label_date}）")
        return

    session = make_session()
    tables = post_and_parse(session,
        url="https://www.taifex.com.tw/cht/3/futContractsDate",
        payload={
            "queryType":    "2",
            "marketCode":   "0",
            "dateaddcnt":   "",
            "queryDate":    label_date,
            "commodity_id": "TXF",
        }
    )
    if tables is None:
        return

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

    if txf is None and subtotal is None:
        return

    def build_record(v):
        if v is None:
            return None
        return {
            "long_txn":      safe_int(v[3]),    # 多方交易口數
            "short_txn":     safe_int(v[5]),    # 空方交易口數
            "net_txn":       safe_int(v[7]),    # 交易淨口數（當日）
            "net_txn_amount":safe_int(v[8]),    # 交易淨額契約金額
            "long_oi":       safe_int(v[9]),    # 多方未平倉
            "short_oi":      safe_int(v[11]),   # 空方未平倉
            "net_oi":        safe_int(v[13]),   # 淨未平倉口數 ★
            "net_oi_amount": safe_int(v[14]),   # 淨未平倉契約金額 ★
        }

    record = {
        "date":     label_date,
        "txf":      build_record(txf),       # 台股期貨
        "subtotal": build_record(subtotal),  # 期貨小計
    }

    records = load_json(FUTURES_JSON)
    records.append(record)
    save_json(FUTURES_JSON, records)

    if record["txf"]:
        net = record["txf"]["net_oi"]
        amt = record["txf"]["net_oi_amount"]
        direction = "淨多" if net > 0 else ("淨空" if net < 0 else "持平")
        print(f"  ✓ 台股期貨：淨未平倉 = {net:+,} 口（{direction}），{amt:,} 千元")
    if record["subtotal"]:
        net = record["subtotal"]["net_oi"]
        amt = record["subtotal"]["net_oi_amount"]
        direction = "淨多" if net > 0 else ("淨空" if net < 0 else "持平")
        print(f"  ✓ 期貨小計：淨未平倉 = {net:+,} 口（{direction}），{amt:,} 千元")


# ============================================================
# 模組2：外資選擇權 Call/Put 未平倉與淨部位
# URL: /cht/3/callsAndPutsDate
#
# 此頁面每個身份別有兩列：買權（Call）和賣權（Put）
# 欄位 index（攤平後共 16 欄）：
#  [0]  序號      [1] 商品名稱   [2] 權別（買權/賣權）  [3] 身份別
#  [4]  買方口數               [5]  買方契約金額
#  [6]  賣方口數               [7]  賣方契約金額
#  [8]  買賣差額口數            [9]  買賣差額契約金額
#  [10] 買方未平倉口數          [11] 買方未平倉契約金額
#  [12] 賣方未平倉口數          [13] 賣方未平倉契約金額
#  [14] 淨未平倉口數 ★         [15] 淨未平倉契約金額
#
# 分析重點：
#   外資買 Call 多 → 看多
#   外資賣 Put 多  → 看多（願意在低點承接）
#   net_call_oi > 0 → 外資 Call 淨多單（看漲）
#   net_put_oi < 0  → 外資 Put 淨空單（賣出保護，看漲）
# ============================================================

def fetch_options(query_date, label_date):
    print(f"▶ 模組2：外資選擇權 Call/Put 部位 (日期: {label_date}, 查詢: {query_date})")

    if already_exists(OPTIONS_JSON, label_date):
        print(f"  今日資料已存在，跳過（{label_date}）")
        return

    session = make_session()
    tables = post_and_parse(session,
        url="https://www.taifex.com.tw/cht/3/callsAndPutsDate",
        payload={
            "queryType":    "4",
            "queryDate":    label_date,
            "commodity_id": "TXO",
        }
    )
    if tables is None:
        return

    df = flatten_cols(tables[0])

    # 同時篩選「臺指選擇權」＋「外資」，避免抓到其他商品的外資列
    mask = df.apply(
        lambda r: r.astype(str).str.contains("外資").any() and
                  r.astype(str).str.contains("臺指選擇權").any(),
        axis=1
    )
    rows = df[mask]

    if len(rows) < 2:
        print(f"  [警告] 找到 {len(rows)} 列，預期 2 列（買權＋賣權）")
        print(rows.to_string())
        return

    call_row = None
    put_row  = None

    for _, row in rows.iterrows():
        cp = str(row.iloc[2]).strip()   # [02] 權別
        if "買權" in cp:
            call_row = row.values
        elif "賣權" in cp:
            put_row = row.values

    if call_row is None or put_row is None:
        print("  [警告] 無法區分買權/賣權列")
        return

    # 欄位對應（已確認）：
    # [04] 買方交易口數  [06] 賣方交易口數  [08] 買賣差額交易口數
    # [10] 買方未平倉    [12] 賣方未平倉    [14] 買賣差額未平倉（=買方-賣方）
    record = {
        "date":           label_date,
        # Call 部位
        "call_buy_txn":   safe_int(call_row[4]),    # 外資買方 Call 交易口數
        "call_sell_txn":  safe_int(call_row[6]),    # 外資賣方 Call 交易口數
        "call_buy_oi":    safe_int(call_row[10]),   # 外資買方 Call 未平倉
        "call_sell_oi":   safe_int(call_row[12]),   # 外資賣方 Call 未平倉
        "net_call_oi":    safe_int(call_row[14]),   # 外資 Call 淨未平倉 ★
        # Put 部位
        "put_buy_txn":    safe_int(put_row[4]),     # 外資買方 Put 交易口數
        "put_sell_txn":   safe_int(put_row[6]),     # 外資賣方 Put 交易口數
        "put_buy_oi":     safe_int(put_row[10]),    # 外資買方 Put 未平倉
        "put_sell_oi":    safe_int(put_row[12]),    # 外資賣方 Put 未平倉
        "net_put_oi":     safe_int(put_row[14]),    # 外資 Put 淨未平倉 ★
    }

    records = load_json(OPTIONS_JSON)
    records.append(record)
    save_json(OPTIONS_JSON, records)

    call_dir = "淨買Call↑" if record["net_call_oi"] > 0 else "淨賣Call↓"
    put_dir  = "淨賣Put↑"  if record["net_put_oi"]  < 0 else "淨買Put↓"
    print(f"  ✓ 寫入成功")
    print(f"    外資 Call 淨未平倉 = {record['net_call_oi']:+,}（{call_dir}）")
    print(f"    外資 Put  淨未平倉 = {record['net_put_oi']:+,}（{put_dir}）")


# ============================================================
# 模組3：全市場 Put/Call Ratio 歷史
# URL: /cht/3/pcRatio（GET 即可，回傳最近20個交易日）
#
# 欄位：日期 | 賣權成交量 | 買權成交量 | 買賣權成交量比率%
#       | 賣權未平倉量 | 買權未平倉量 | 買賣權未平倉量比率%
#
# 只取當日那筆（第一列），append 進歷史
# ============================================================

def fetch_pc_ratio(query_date, label_date):
    print(f"▶ 模組3：全市場 P/C Ratio (日期: {label_date}, 查詢: {query_date})")

    if already_exists(PC_JSON, label_date):
        print(f"  今日資料已存在，跳過（{label_date}）")
        return

    session = make_session()
    try:
        resp = session.get(
            "https://www.taifex.com.tw/cht/3/pcRatio",
            timeout=30
        )
        resp.encoding = "utf-8"
        tables = pd.read_html(StringIO(resp.text))
    except Exception as e:
        print(f"  [錯誤] {e}")
        return

    if not tables:
        print("  [警告] 無資料")
        return

    df = tables[0]

    # 找今日那列（日期欄格式：2026/5/5）
    # 轉換 TODAY_LABEL 為可能的格式（去掉補零）
    today_variants = [
        label_date,                                          # 2026/05/05
        label_date.replace("/0", "/").replace("/0", "/"),    # 2026/5/5
    ]

    today_row = None
    for _, row in df.iterrows():
        date_val = str(row.iloc[0]).strip()
        if any(date_val == v for v in today_variants):
            today_row = row
            break

    if today_row is None:
        print(f"  [警告] 找不到 {label_date} 的資料（pcRatio 只保留最近20個交易日）")
        today_row = df.iloc[0]
        print(f"  [提示] 以最新一筆資料代替：{today_row.iloc[0]}")

    put_vol  = safe_int(today_row.iloc[1])
    call_vol = safe_int(today_row.iloc[2])
    pc_vol   = safe_float(today_row.iloc[3])
    put_oi   = safe_int(today_row.iloc[4])
    call_oi  = safe_int(today_row.iloc[5])
    pc_oi    = safe_float(today_row.iloc[6])

    record = {
        "date":     label_date,
        "put_vol":  put_vol,     # Put 成交量
        "call_vol": call_vol,    # Call 成交量
        "pc_vol":   pc_vol,      # 成交量比率%
        "put_oi":   put_oi,      # Put 未平倉
        "call_oi":  call_oi,     # Call 未平倉
        "pc_oi":    pc_oi,       # 未平倉比率% ★ 核心指標
    }

    records = load_json(PC_JSON)
    records.append(record)
    save_json(PC_JSON, records)

    sentiment = "偏空" if pc_oi and pc_oi > 120 else ("偏多" if pc_oi and pc_oi < 80 else "中立")
    print(f"  ✓ 寫入成功：P/C未平倉比率 = {pc_oi}%（{sentiment}）")


# ============================================================
# 主程式
# ============================================================

if __name__ == "__main__":
    print(f"=== 期交所資料抓取 {TODAY_LABEL} ===\n")

    if date.today().weekday() >= 5:
        print("今日為週末，無交易資料，結束執行。")
        sys.exit(0)

    os.makedirs(DATA_DIR, exist_ok=True)

    fetch_futures(TODAY_QUERY, TODAY_LABEL)
    print()
    fetch_options(TODAY_QUERY, TODAY_LABEL)
    print()
    fetch_pc_ratio(TODAY_QUERY, TODAY_LABEL)
    print()
    options_analysis.fetch_oi_strike(TODAY_LABEL, TODAY_LABEL)
    print()
    print()
    fetch_stock_net(TODAY_QUERY.replace("-", ""), TODAY_LABEL)
    print()

    print("\n=== 完成 ===")
    print(f"\n產出檔案：")
    for f in [FUTURES_JSON, OPTIONS_JSON, PC_JSON, options_analysis.OI_STRIKE_JSON, STOCK_NET_JSON]:
        if os.path.exists(f):
            records = load_json(f)
            count = len(records) if isinstance(records, list) else 1
            print(f"  {f}（{count} 筆）")