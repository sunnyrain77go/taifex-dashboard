import os
import pandas as pd
from io import StringIO

from config import DATA_DIR
from utils import load_json, save_json, make_session

# 新增一個 JSON 檔路徑
OI_STRIKE_JSON = os.path.join(DATA_DIR, "oi_strike.json")

def fetch_oi_strike(query_date, label_date):
    """
    抓取全市場選擇權各履約價 OI 分布
    - 自動辨識當週週選 (Weekly) 與 近月月選 (Monthly)
    - 計算壓力/支撐帶 (Top 3) 與 集中度
    - 產生多空解讀訊號
    """
    print(f"> 選擇權各履約價 OI 分布（週選＋月選分離分析） ({query_date})")

    session = make_session()
    # 先瀏覽頁面獲取必要 Cookie
    session.get("https://www.taifex.com.tw/cht/3/dlOptDailyMarketView", timeout=15)

    # 執行下載
    r = session.post(
        "https://www.taifex.com.tw/cht/3/dlOptDataDown",
        data={
            "down_type":      "1",
            "commodity_id":   "TXO",
            "commodity_id2":  "",
            "queryStartDate": label_date,   # 格式 2026/05/05
            "queryEndDate":   label_date,
            "button3":        "下載",
        },
        timeout=30
    )

    if r.status_code != 200:
        print(f"  [錯誤] 請求失敗 HTTP {r.status_code}")
        return

    try:
        # 轉換編碼並讀取 CSV
        text = r.content.decode("big5")
        df = pd.read_csv(StringIO(text))
        df.columns = df.columns.str.strip()
    except Exception as e:
        print(f"  [錯誤] 解析 CSV 失敗：{e}")
        return

    # ── 篩選條件
    # 1. 一般時段（排除盤後）
    # 2. 近月（202605）＋當週選擇權（202605W1 第一個週別）
    # 3. 有未沖銷契約數

    df["未沖銷契約數"] = pd.to_numeric(df["未沖銷契約數"], errors="coerce")
    df["履約價"]      = pd.to_numeric(df["履約價"],       errors="coerce")
    df["到期月份_clean"] = df["到期月份(週別)"].astype(str).str.strip()

    # --- 合約辨識邏輯 ---
    # 找所有合約的到期日
    from datetime import datetime as dt
    query_dt = dt.strptime(query_date, "%Y-%m-%d") if "-" in query_date else dt.strptime(query_date, "%Y/%m/%d")
    
    unique_contracts = df["到期月份_clean"].unique()
    contract_expiry = {}
    for c in unique_contracts:
        # 取該週別的契約到期日
        exp_vals = df[df["到期月份_clean"] == c]["契約到期日"].dropna().unique()
        if len(exp_vals) > 0:
            try:
                # 轉成 datetime 方便比較
                exp_dt = dt.strptime(str(int(exp_vals[0])), "%Y%m%d")
                contract_expiry[c] = exp_dt
            except Exception:
                continue

    # 1. 找最近到期的週選 (代碼含 W 且 到期日 >= 查詢日)
    weeklies = [c for c in contract_expiry if "W" in c and contract_expiry[c] >= query_dt]
    nearest_week = None
    nearest_expiry = None
    if weeklies:
        nearest_week = min(weeklies, key=lambda x: contract_expiry[x])
        nearest_expiry = contract_expiry[nearest_week]

    # 2. 找最近到期的月選 (代碼為 6 位純數字 且 到期日 >= 查詢日)
    monthlies = [c for c in contract_expiry if len(c) == 6 and c.isdigit() and contract_expiry[c] >= query_dt]
    near_month = None
    if monthlies:
        near_month = min(monthlies, key=lambda x: contract_expiry[x])

    print(f"  週選合約：{nearest_week}（到期：{nearest_expiry.strftime('%Y/%m/%d') if nearest_expiry else 'N/A'}）")
    print(f"  月選合約：{near_month}")

    # --- 資料分流 ---
    base_mask = (
        (df["交易時段"] == "一般") &
        (df["未沖銷契約數"].notna()) &
        (df["未沖銷契約數"] > 0)
    )

    df_week  = df[base_mask & (df["到期月份_clean"] == nearest_week)].copy()
    df_month = df[base_mask & (df["到期月份_clean"] == near_month)].copy()

    # --- 彙總與分析函式 ---
    def build_oi_map(df_src):
        """回傳 {履約價: {call_oi, put_oi}} dict"""
        res = {}
        for _, row in df_src.iterrows():
            strike = row["履約價"]
            cp = str(row["買賣權"]).strip()
            oi = int(row["未沖銷契約數"])
            if strike not in res:
                res[strike] = {"call_oi": 0, "put_oi": 0}
            if cp == "買權": res[strike]["call_oi"] += oi
            elif cp == "賣權": res[strike]["put_oi"] += oi
        return res

    week_map  = build_oi_map(df_week)
    month_map = build_oi_map(df_month)

    # 讀取舊資料算增減
    existing = load_json(OI_STRIKE_JSON)
    prev_record = existing[-1] if existing and isinstance(existing, list) else None

    def get_prev_map(prev_rec, key):
        """從前一日 record 取 {履約價: {call_oi, put_oi}}"""
        if not prev_rec:
            return {}
        return {
            s["strike"]: s
            for s in prev_rec.get(key, {}).get("strikes", [])
        }

    prev_week_map  = get_prev_map(prev_record, "weekly")
    prev_month_map = get_prev_map(prev_record, "monthly")

    # ── 建立 strikes list
    def build_strikes(oi_map, prev_map):
        """只保留 Call 前10 和 Put 前10，其餘丟棄"""
        all_strikes = []
        total_call = sum(v["call_oi"] for v in oi_map.values())
        total_put  = sum(v["put_oi"]  for v in oi_map.values())

        for strike in sorted(oi_map.keys()):
            v        = oi_map[strike]
            prev     = prev_map.get(strike, {})
            call_chg = v["call_oi"] - prev.get("call_oi", 0)
            put_chg  = v["put_oi"]  - prev.get("put_oi",  0)
            all_strikes.append({
                "strike":   int(strike),
                "call_oi":  v["call_oi"],
                "put_oi":   v["put_oi"],
                "call_chg": call_chg,
                "put_chg":  put_chg,
            })

        # 各取前10，取聯集
        top10_call    = sorted(all_strikes, key=lambda x: x["call_oi"], reverse=True)[:10]
        top10_put     = sorted(all_strikes, key=lambda x: x["put_oi"],  reverse=True)[:10]
        top10_strikes = {s["strike"]: s for s in top10_call + top10_put}  # 去重

        return list(top10_strikes.values()), total_call, total_put

    week_strikes,  w_total_call, w_total_put  = build_strikes(week_map,  prev_week_map)
    month_strikes, m_total_call, m_total_put  = build_strikes(month_map, prev_month_map)

    # ── 分析函式
    def analyze(strikes, total_call, total_put, label):
        if not strikes:
            return {}

        # 直接從前5找最大
        max_call = max(strikes, key=lambda x: x["call_oi"])
        max_put  = max(strikes, key=lambda x: x["put_oi"])

        # OI 變動（增加與減少最多）
        max_call_chg = max(strikes, key=lambda x: x["call_chg"])
        max_put_chg  = max(strikes, key=lambda x: x["put_chg"])
        max_call_dec = min(strikes, key=lambda x: x["call_chg"])
        max_put_dec  = min(strikes, key=lambda x: x["put_chg"])

        # 壓力帶：Call 前10的範圍
        call_strikes_sorted = sorted(strikes, key=lambda x: x["call_oi"], reverse=True)[:10]
        put_strikes_sorted  = sorted(strikes, key=lambda x: x["put_oi"],  reverse=True)[:10]
        call_range = (
            min(x["strike"] for x in call_strikes_sorted),
            max(x["strike"] for x in call_strikes_sorted)
        )
        put_range = (
            min(x["strike"] for x in put_strikes_sorted),
            max(x["strike"] for x in put_strikes_sorted)
        )

        # 集中度
        call_concentration = round(max_call["call_oi"] / total_call * 100, 1) if total_call > 0 else 0
        put_concentration  = round(max_put["put_oi"]   / total_put  * 100, 1) if total_put  > 0 else 0

        print(f"  [{label}] 壓力區：{call_range[0]:,}–{call_range[1]:,}，支撐區：{put_range[0]:,}–{put_range[1]:,}")
        print(f"  [{label}] Call 增減最多：{max_call_chg['strike']}({max_call_chg['call_chg']:+,}) / {max_call_dec['strike']}({max_call_dec['call_chg']:+,})")
        print(f"  [{label}] Put  增減最多：{max_put_chg['strike']}({max_put_chg['put_chg']:+,}) / {max_put_dec['strike']}({max_put_dec['put_chg']:+,})")
        print(f"  [{label}] Call 集中度={call_concentration}%，Put 集中度={put_concentration}%")

        return {
            "total_call_oi":       total_call,
            "total_put_oi":        total_put,
            "max_call_strike":     max_call["strike"],
            "max_call_oi":         max_call["call_oi"],
            "max_put_strike":      max_put["strike"],
            "max_put_oi":          max_put["put_oi"],
            "top2_call":           [{"strike": x["strike"], "oi": x["call_oi"]} for x in call_strikes_sorted[:2]],
            "top2_put":            [{"strike": x["strike"], "oi": x["put_oi"]}  for x in put_strikes_sorted[:2]],
            "call_range":          {"low": call_range[0], "high": call_range[1]},
            "put_range":           {"low": put_range[0],  "high": put_range[1]},
            "call_concentration":  call_concentration,
            "put_concentration":   put_concentration,
            "max_call_chg_strike": max_call_chg["strike"],
            "max_call_chg":        max_call_chg["call_chg"],
            "max_call_dec_strike": max_call_dec["strike"],
            "max_call_dec":        max_call_dec["call_chg"],
            "max_put_chg_strike":  max_put_chg["strike"],
            "max_put_chg":         max_put_chg["put_chg"],
            "max_put_dec_strike":  max_put_dec["strike"],
            "max_put_dec":         max_put_dec["put_chg"],
            "top10": sorted(strikes, key=lambda x: x["strike"]),
        }

    weekly_result  = analyze(week_strikes,  w_total_call, w_total_put,  "週選")
    monthly_result = analyze(month_strikes, m_total_call, m_total_put, "月選")

    # ── 異常警報判斷
    def gen_signal(weekly, monthly):
        if not weekly or not monthly:
            return [{"type": "資料不足", "desc": "週選或月選資料缺失"}]

        # 印出前兩大 OI 摘要
        print("  [籌碼分佈摘要]")
        for label, data in [("週選", weekly), ("月選", monthly)]:
            c1, c2 = data["top2_call"][0], data["top2_call"][1]
            p1, p2 = data["top2_put"][0],  data["top2_put"][1]
            print(f"    {label} Call Top2: {c1['strike']}({c1['oi']:,}), {c2['strike']}({c2['oi']:,})")
            print(f"    {label} Put  Top2: {p1['strike']}({p1['oi']:,}), {p2['strike']}({p2['oi']:,})")

        w_res = weekly["max_call_strike"]    # 週選壓力
        w_sup = weekly["max_put_strike"]     # 週選支撐
        m_res = monthly["max_call_strike"]   # 月選壓力
        m_sup = monthly["max_put_strike"]    # 月選支撐

        signals = []

        # 短空長多：週選壓力 < 月選壓力
        if w_res < m_res:
            signals.append({
                "type":  "短空長多",
                "desc":  f"週選壓力({w_res:,}) < 月選壓力({m_res:,})，短線有壓但長線看好，預期震盪偏多",
            })

        # 短多長空：週選支撐 > 月選支撐
        if w_sup > m_sup:
            signals.append({
                "type": "短多長空",
                "desc": f"週選支撐({w_sup:,}) > 月選支撐({m_sup:,})，短線撐住但長線偏弱，需注意月選結算壓力",
            })

        # 方向一致看多
        if w_res >= m_res and w_sup >= m_sup:
            signals.append({
                "type": "多頭一致",
                "desc": f"週選月選壓力支撐對齊，趨勢明確偏多，震盪幅度較小",
            })

        # 方向一致看空
        if w_res <= m_res and w_sup <= m_sup and not any(s["type"] == "多頭一致" for s in signals):
            signals.append({
                "type": "空頭一致",
                "desc": f"週選月選壓力支撐皆偏低，趨勢偏空，反彈空間有限",
            })

        # 結算磁吸（週選最大OI集中度高）
        if weekly.get("call_concentration", 0) > 30 or weekly.get("put_concentration", 0) > 30:
            signals.append({
                "type": "結算磁吸",
                "desc": f"週選OI高度集中，結算前指數可能往 {w_res:,}（壓）或 {w_sup:,}（撐）靠攏",
            })

        return signals if signals else [{"type": "中立", "desc": "週選月選無明顯異常訊號"}]

    signals = gen_signal(weekly_result, monthly_result)
    for s in signals:
        print(f"  ! 訊號：{s['type']} - {s['desc']}")
    # --- 儲存資料 ---
    record = {
        "date": label_date,
        "weekly": {
            "expiry": nearest_week,
            "expiry_date": nearest_expiry.strftime("%Y/%m/%d") if nearest_expiry else None,
            **weekly_result,
        },
        "monthly": {
            "expiry": near_month,
            **monthly_result,
        },
        "signals": signals
    }

    # 更新或新增 JSON
    if isinstance(existing, list):
        # 如果今天已存在就更新，否則 append
        found = False
        for i, rec in enumerate(existing):
            if rec.get("date") == label_date:
                existing[i] = record
                found = True
                break
        if not found:
            existing.append(record)
        save_json(OI_STRIKE_JSON, existing)
    else:
        save_json(OI_STRIKE_JSON, [record])

    print(f"  [OK] 寫入成功：週選 {len(week_strikes)} 個履約價，月選 {len(month_strikes)} 個履約價")

if __name__ == "__main__":
    # 直接指定日期
    target = "2026/04/27"
    fetch_oi_strike(target, target)
