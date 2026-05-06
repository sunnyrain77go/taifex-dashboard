#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_prompt.py
讀取 data/ 資料夾的所有 JSON，自動填入當日數值，產生分析 prompt

用法：
  python gen_prompt.py              # 使用最新一筆資料
  python gen_prompt.py 2026/05/05  # 指定日期
"""

import json
import os
import sys
from datetime import datetime

DATA_DIR = "data"

# ============================================================
# 工具函式
# ============================================================

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def find_record(records, date_label):
    """從 list 裡找指定日期的那筆，找不到回傳最後一筆"""
    if not records:
        return None
    if date_label:
        for r in records:
            if r.get("date") == date_label:
                return r
        print(f"  [提示] 找不到 {date_label}，改用最新一筆")
    return records[-1]


def fmt(val, unit="", decimal=0):
    """格式化數字，加正負號"""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if decimal > 0:
            s = f"{v:+.{decimal}f}"
        else:
            s = f"{int(v):+,}"
        return s + unit
    except Exception:
        return str(val)


def fmt_plain(val, unit="", decimal=0):
    """格式化數字，不加正負號"""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if decimal > 0:
            s = f"{v:.{decimal}f}"
        else:
            s = f"{int(v):,}"
        return s + unit
    except Exception:
        return str(val)


# ============================================================
# 讀取各 JSON
# ============================================================

def load_all(date_label=None):
    futures  = find_record(load_json(os.path.join(DATA_DIR, "futures.json")),    date_label)
    options  = find_record(load_json(os.path.join(DATA_DIR, "options_pc.json")), date_label)
    pc       = find_record(load_json(os.path.join(DATA_DIR, "pc_ratio.json")),   date_label)
    oi_list  = load_json(os.path.join(DATA_DIR, "oi_strike.json"))
    oi       = find_record(oi_list, date_label)
    stock    = find_record(load_json(os.path.join(DATA_DIR, "stock_net.json")),  date_label)

    # 前一日期貨（算口數變化）
    futures_all = load_json(os.path.join(DATA_DIR, "futures.json"))
    prev_futures = None
    if futures and futures_all:
        idx = next((i for i, r in enumerate(futures_all) if r.get("date") == futures.get("date")), -1)
        if idx > 0:
            prev_futures = futures_all[idx - 1]

    return futures, options, pc, oi, stock, prev_futures


# ============================================================
# 產生 prompt
# ============================================================

def gen_prompt(date_label=None):
    futures, options, pc, oi, stock, prev_futures = load_all(date_label)

    # 日期
    report_date = (futures or options or stock or {}).get("date", date_label or "N/A")

    # ── 期貨數值
    txf         = (futures or {}).get("txf", {}) or {}
    subtotal    = (futures or {}).get("subtotal", {}) or {}
    net_oi      = txf.get("net_oi")
    net_oi_amt  = txf.get("net_oi_amount")
    sub_net_oi  = subtotal.get("net_oi")
    sub_net_amt = subtotal.get("net_oi_amount")

    # 口數變化（與前日比）
    prev_txf    = (prev_futures or {}).get("txf", {}) or {}
    net_oi_chg  = (net_oi - prev_txf["net_oi"]) if net_oi is not None and prev_txf.get("net_oi") is not None else None

    # ── 選擇權數值
    net_call_oi = (options or {}).get("net_call_oi")
    net_put_oi  = (options or {}).get("net_put_oi")
    pc_oi       = (pc or {}).get("pc_oi")

    # ── OI 分布
    max_call_strike     = (oi or {}).get("max_call_strike")
    max_put_strike      = (oi or {}).get("max_put_strike")
    max_call_chg_strike = (oi or {}).get("max_call_chg_strike")
    max_put_chg_strike  = (oi or {}).get("max_put_chg_strike")

    # 找對應口數
    strikes = (oi or {}).get("strikes", [])
    def find_strike(s):
        return next((x for x in strikes if x.get("strike") == s), {})

    max_call_data     = find_strike(max_call_strike)
    max_put_data      = find_strike(max_put_strike)
    max_call_chg_data = find_strike(max_call_chg_strike)
    max_put_chg_data  = find_strike(max_put_chg_strike)

    # ── 現貨數值
    foreign    = (stock or {}).get("foreign")
    trust      = (stock or {}).get("trust")
    dealer     = (stock or {}).get("dealer_total")
    total      = (stock or {}).get("total")
    foreign_5d = (stock or {}).get("foreign_5d")

    # ============================================================
    # 組合 prompt
    # ============================================================

    prompt = f"""你是一位台灣股市籌碼分析師，專精於期貨選擇權籌碼解讀。
請根據以下當日數據，產出今日外資多空態度分析報告。

## 當日數據（{report_date}）

### 一、台股期貨
- 外資淨未平倉口數：{fmt_plain(net_oi, " 口")}
- 外資淨未平倉金額：{fmt_plain(net_oi_amt, " 千元")}
- 期貨小計淨未平倉口數：{fmt_plain(sub_net_oi, " 口")}
- 期貨小計淨未平倉金額：{fmt_plain(sub_net_amt, " 千元")}
- 與前日口數變化：{fmt(net_oi_chg, " 口") if net_oi_chg is not None else "N/A（無前日資料）"}

### 二、選擇權部位
- 外資 Call 淨未平倉：{fmt(net_call_oi, " 口")}
- 外資 Put 淨未平倉：{fmt(net_put_oi, " 口")}
- 全市場 P/C 未平倉比率：{fmt_plain(pc_oi, "%", 2)}

### 三、履約價 OI 分布（近月＋當週）
- 最大 Call 壓力履約價：{fmt_plain(max_call_strike)}（{fmt_plain(max_call_data.get('call_oi'), ' 口')}）
- 最大 Put 支撐履約價：{fmt_plain(max_put_strike)}（{fmt_plain(max_put_data.get('put_oi'), ' 口')}）
- Call OI 增加最多履約價：{fmt_plain(max_call_chg_strike)}（增加 {fmt(max_call_chg_data.get('call_chg'), ' 口')}）
- Put OI 增加最多履約價：{fmt_plain(max_put_chg_strike)}（增加 {fmt(max_put_chg_data.get('put_chg'), ' 口')}）

### 四、現貨三大法人買賣超
- 外資現貨買賣超：{fmt(foreign, ' 億元', 2)}
- 投信買賣超：{fmt(trust, ' 億元', 2)}
- 自營商買賣超：{fmt(dealer, ' 億元', 2)}
- 三大法人合計：{fmt(total, ' 億元', 2)}
- 外資近5日累計買賣超：{fmt(foreign_5d, ' 億元', 2)}

## 分析架構

請依序輸出以下六個段落，每段2至3句：

### 1. 整體多空傾向
綜合所有數據，用一句話判斷今日外資整體態度。
可選擇：積極看多、偏多觀望、中立、偏空避險、積極看空。

### 2. 期貨籌碼解讀
說明淨未平倉口數與金額的意義，以及與前日變化代表的主力態度（加碼/減碼/方向改變）。

### 3. 選擇權籌碼解讀
解讀 Call/Put 淨未平倉方向，P/C 比率的市場情緒，以及最大壓力與支撐區間對近期行情的影響。

### 4. OI 增減主力佈局
說明 OI 增加最多的 Call/Put 履約價代表主力在哪裡加碼，以及這對行情的暗示。

### 5. 期現貨交叉驗證
比較現貨買賣超與期貨部位方向是否一致。若一致則強化訊號；若不一致則說明可能是避險或套利操作。

### 6. 風險提示
指出數據中的矛盾訊號、極端值、或需要謹慎解讀的地方，避免過度解讀單一指標。

## 輸出要求
- 繁體中文
- 重要數字與價位用**粗體**標示
- 每段簡潔，不超過3句
- 結尾單獨一行：「📊 今日信號：[積極看多／偏多觀望／中立／偏空避險／積極看空]」
"""

    return prompt, report_date


# ============================================================
# 主程式
# ============================================================

if __name__ == "__main__":
    # 可指定日期：python gen_prompt.py 2026/05/05
    target_date = sys.argv[1] if len(sys.argv) > 1 else None

    prompt, report_date = gen_prompt(target_date)

    # 印出 prompt
    print(prompt)

    # 同時存成 txt 檔，方便複製
    output_path = os.path.join(DATA_DIR, "prompt_latest.txt")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(prompt)

    print(f"\n{'='*50}")
    print(f"✓ prompt 已儲存至 {output_path}")
    print(f"  直接複製貼給 Claude 或 ChatGPT 即可")