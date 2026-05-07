#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_prompt.py
讀取 data/ 資料夾的所有 JSON，自動填入當日數值，產生分析 prompt
整合了週月選分離分析、Top 10 表格、以及自動化分析訊號。

用法：
  python gen_prompt.py              # 使用最新一筆資料
  python gen_prompt.py 2026/05/05  # 指定日期
"""

import json
import os
import sys

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
    """加正負號"""
    if val is None: return "N/A"
    try:
        v = float(val)
        s = f"{v:+.{decimal}f}" if decimal > 0 else f"{int(v):+}"
        return s + unit
    except Exception: return str(val)


def fmt_plain(val, unit="", decimal=0):
    """不加正負號"""
    if val is None: return "N/A"
    try:
        v = float(val)
        s = f"{v:.{decimal}f}" if decimal > 0 else f"{int(v):,}"
        return s + unit
    except Exception: return str(val)


def top10_table(strikes, mode="call"):
    """把 top10 list 格式化成文字表"""
    if not strikes: return "    （無資料）"
    key     = f"{mode}_oi"
    chg_key = f"{mode}_chg"
    # 依 OI 大小排序
    sorted_list = sorted(strikes, key=lambda x: x.get(key, 0), reverse=True)[:10]
    
    lines = ["    履約價      OI     增減"]
    for s in sorted_list:
        oi_val  = s.get(key, 0)
        chg_val = s.get(chg_key, 0)
        chg_str = f"{chg_val:+,}" if chg_val is not None else "N/A"
        lines.append(f"    {s['strike']:>7,}  {oi_val:>7,}  {chg_str:>7}")
    return "\n".join(lines)


# ============================================================
# 讀取資料
# ============================================================

def load_all(date_label=None):
    futures  = find_record(load_json(os.path.join(DATA_DIR, "futures.json")),    date_label)
    options  = find_record(load_json(os.path.join(DATA_DIR, "options_pc.json")), date_label)
    pc       = find_record(load_json(os.path.join(DATA_DIR, "pc_ratio.json")),   date_label)
    oi       = find_record(load_json(os.path.join(DATA_DIR, "oi_strike.json")),  date_label)
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
# 產生 Prompt
# ============================================================

def gen_prompt(date_label=None):
    futures, options, pc, oi, stock, prev_futures = load_all(date_label)
    report_date = (futures or options or stock or {}).get("date", date_label or "N/A")

    # ── 期貨
    txf        = (futures or {}).get("txf", {}) or {}
    subtotal   = (futures or {}).get("subtotal", {}) or {}
    net_oi     = txf.get("net_oi")
    net_oi_amt = txf.get("net_oi_amount")
    sub_net_oi = subtotal.get("net_oi")
    sub_net_amt= subtotal.get("net_oi_amount")
    
    prev_txf   = (prev_futures or {}).get("txf", {}) or {}
    net_oi_chg = (net_oi - prev_txf["net_oi"]) if net_oi is not None and prev_txf.get("net_oi") is not None else None

    # ── 選擇權
    net_call_oi = (options or {}).get("net_call_oi")
    net_put_oi  = (options or {}).get("net_put_oi")
    pc_oi       = (pc or {}).get("pc_oi")

    # ── OI 週選/月選
    weekly  = (oi or {}).get("weekly",  {}) or {}
    monthly = (oi or {}).get("monthly", {}) or {}
    signals = (oi or {}).get("signals", [])

    def get_oi_info(data):
        return {
            "expiry":    data.get("expiry_date", data.get("expiry", "N/A")),
            "max_call":  data.get("max_call_strike"),
            "max_call_oi": data.get("max_call_oi"),
            "max_put":   data.get("max_put_strike"),
            "max_put_oi":  data.get("max_put_oi"),
            "c_range":   data.get("call_range", {}),
            "p_range":   data.get("put_range", {}),
            "c_conc":    data.get("call_concentration"),
            "p_conc":    data.get("put_concentration"),
            "c_chg_s":   data.get("max_call_chg_strike"),
            "c_chg":     data.get("max_call_chg"),
            "p_chg_s":   data.get("max_put_chg_strike"),
            "p_chg":     data.get("max_put_chg"),
            "c_dec_s":   data.get("max_call_dec_strike"),
            "c_dec":     data.get("max_call_dec"),
            "p_dec_s":   data.get("max_put_dec_strike"),
            "p_dec":     data.get("max_put_dec"),
            "top10":     data.get("top10", [])
        }

    w = get_oi_info(weekly)
    m = get_oi_info(monthly)

    signal_text = "".join([f"  ⚡ {s['type']}：{s['desc']}\n" for s in signals]) if signals else "  （無異常訊號）\n"

    # ── 現貨
    foreign    = (stock or {}).get("foreign")
    trust      = (stock or {}).get("trust")
    dealer     = (stock or {}).get("dealer_total")
    total      = (stock or {}).get("total")
    foreign_5d = (stock or {}).get("foreign_5d")

    # ============================================================
    # 組合 Prompt 文字
    # ============================================================

    prompt = f"""你是一位台灣股市籌碼分析師，專精於期貨選擇權籌碼解讀。
請根據以下當日數據，產出今日外資多空態度分析報告。

## 當日數據（{report_date}）

### 一、台股期貨
- 外資淨未平倉口數：{fmt_plain(net_oi, " 口")}
- 外資淨未平倉金額：{fmt_plain(net_oi_amt, " 千元")}
- 期貨小計淨未平倉口數：{fmt_plain(sub_net_oi, " 口")}
- 與前日口數變化：{fmt(net_oi_chg, " 口") if net_oi_chg is not None else "N/A"}

### 二、選擇權部位
- 外資 Call 淨未平倉：{fmt(net_call_oi, " 口")}
- 外資 Put 淨未平倉：{fmt(net_put_oi, " 口")}
- 全市場 P/C 未平倉比率：{fmt_plain(pc_oi, "%", 2)}

### 三、【短線堡壘】週選 OI（到期：{w['expiry']}）
- 最大 Call 壓力：{fmt_plain(w['max_call'])}（{fmt_plain(w['max_call_oi'], " 口")}，集中度 {fmt_plain(w['c_conc'], "%", 1)}）
- 最大 Put 支撐：{fmt_plain(w['max_put'])}（{fmt_plain(w['max_put_oi'], " 口")}，集中度 {fmt_plain(w['p_conc'], "%", 1)}）
- 壓力帶：{fmt_plain(w['c_range'].get('low'))} ～ {fmt_plain(w['c_range'].get('high'))}
- 支撐帶：{fmt_plain(w['p_range'].get('low'))} ～ {fmt_plain(w['p_range'].get('high'))}
- OI 加碼最多：Call {fmt_plain(w['c_chg_s'])} ({fmt(w['c_chg'])}) / Put {fmt_plain(w['p_chg_s'])} ({fmt(w['p_chg'])})
- OI 減少最多：Call {fmt_plain(w['c_dec_s'])} ({fmt(w['c_dec'])}) / Put {fmt_plain(w['p_dec_s'])} ({fmt(w['p_dec'])})

週選 Call Top10：
{top10_table(w['top10'], 'call')}

週選 Put Top10：
{top10_table(w['top10'], 'put')}

### 四、【戰略重鎮】月選 OI（到期：{m['expiry']}）
- 最大 Call 壓力：{fmt_plain(m['max_call'])}（{fmt_plain(m['max_call_oi'], " 口")}，集中度 {fmt_plain(m['c_conc'], "%", 1)}）
- 最大 Put 支撐：{fmt_plain(m['max_put'])}（{fmt_plain(m['max_put_oi'], " 口")}，集中度 {fmt_plain(m['p_conc'], "%", 1)}）
- OI 加碼最多：Call {fmt_plain(m['c_chg_s'])} ({fmt(m['c_chg'])}) / Put {fmt_plain(m['p_chg_s'])} ({fmt(m['p_chg'])})

月選 Call Top10：
{top10_table(m['top10'], 'call')}

月選 Put Top10：
{top10_table(m['top10'], 'put')}

### 五、【異常警報】交叉訊號
{signal_text}
### 六、現貨三大法人買賣超
- 外資現貨買賣超：{fmt(foreign, " 億元", 2)}
- 投信買賣超：{fmt(trust, " 億元", 2)}
- 三大法人合計：{fmt(total, " 億元", 2)}
- 外資近5日累計買賣超：{fmt(foreign_5d, " 億元", 2)}

## 分析架構（請依序輸出以下七個段落，每段2至3句）

1. **整體多空傾向**：判斷外資整體態度（積極看多/偏多觀望/中立/偏空避險/積極看空）。
2. **期貨籌碼解讀**：說明淨未平倉變化代表的主力態度。
3. **選擇權部位解讀**：解讀 Call/Put 淨部位與 P/C 比率情緒。
4. **短線堡壘（週選）解讀**：說明結算前支撐壓力，以及 OI 集中度代表的磁吸強度。
5. **戰略重鎮（月選）解讀**：說明本月總體防線與中期佈局方向。
6. **異常警報解讀**：針對交叉訊號說明短線與波段的分歧或一致性。
7. **期現貨交叉驗證與風險提示**：比較現貨買賣超與期貨方向，並指出矛盾訊號。

## 輸出要求
- 繁體中文，重要數字與價位用**粗體**標示。
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
    print(f"  直接複製貼給 AI 進行分析即可")