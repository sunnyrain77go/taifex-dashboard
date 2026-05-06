import os
import pandas as pd
from io import StringIO

from config import DATA_DIR
from utils import load_json, save_json, make_session

# 新增一個 JSON 檔路徑
OI_STRIKE_JSON = os.path.join(DATA_DIR, "oi_strike.json")

def fetch_oi_strike(query_date, label_date):
    print("▶ 模組4：各履約價 OI 分布（近月＋當週）")

    session = make_session()

    # 先 GET 頁面取 cookie
    session.get("https://www.taifex.com.tw/cht/3/dlOptDailyMarketView", timeout=15)

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
        print(f"  [錯誤] HTTP {r.status_code}")
        return

    try:
        text = r.content.decode("big5")
        df = pd.read_csv(StringIO(text))
        df.columns = df.columns.str.strip()
    except Exception as e:
        print(f"  [錯誤] 解析失敗：{e}")
        return

    # ── 篩選條件
    # 1. 一般時段（排除盤後）
    # 2. 近月（202605）＋當週選擇權（202605W1 第一個週別）
    # 3. 有未沖銷契約數

    df["未沖銷契約數"] = pd.to_numeric(df["未沖銷契約數"], errors="coerce")
    df["履約價"]      = pd.to_numeric(df["履約價"],       errors="coerce")

    # 找近月代碼：格式 YYYYMM，取當月
    year_month = label_date[:7].replace("/", "")   # "202605"

    # 近月：YYYYMM + 空白（如 "202605  "）
    # 當週：YYYYMMW1（當月第一個週選）
    near_month = year_month          # "202605"
    week1      = year_month + "W1"   # "202605W1"

    df["到期月份_clean"] = df["到期月份(週別)"].astype(str).str.strip()

    mask = (
        (df["交易時段"] == "一般") &
        (df["未沖銷契約數"].notna()) &
        (df["未沖銷契約數"] > 0) &
        (df["到期月份_clean"].isin([near_month, week1]))
    )
    df_f = df[mask].copy()

    if df_f.empty:
        print(f"  [警告] 篩選後無資料，到期月份種類：{df['到期月份_clean'].unique()}")
        return

    print(f"  篩選後：{len(df_f)} 列（近月={near_month}, 週選={week1}）")

    # ── 讀取前一日資料，計算 OI 增減
    existing = load_json(OI_STRIKE_JSON)
    prev_data = None
    if isinstance(existing, list) and len(existing) > 0:
        prev_data = existing[-1]   # 最後一筆

    def build_oi_map(df_src, cp_type):
        """回傳 {履約價: OI} 的 dict"""
        filtered = df_src[df_src["買賣權"] == cp_type]
        grouped  = filtered.groupby("履約價")["未沖銷契約數"].sum()
        return {float(k): int(v) for k, v in grouped.items()}

    call_map = build_oi_map(df_f, "買權")
    put_map  = build_oi_map(df_f, "賣權")

    # 前一日 OI map（用來算增減）
    prev_call_map = {}
    prev_put_map  = {}
    if prev_data:
        for s in prev_data.get("strikes", []):
            k = float(s["strike"])
            prev_call_map[k] = s.get("call_oi", 0)
            prev_put_map[k]  = s.get("put_oi",  0)

    # ── 整合所有履約價
    all_strikes = sorted(set(list(call_map.keys()) + list(put_map.keys())))

    strikes_out = []
    for strike in all_strikes:
        call_oi  = call_map.get(strike, 0)
        put_oi   = put_map.get(strike,  0)
        call_chg = call_oi - prev_call_map.get(strike, 0)
        put_chg  = put_oi  - prev_put_map.get(strike,  0)

        strikes_out.append({
            "strike":   int(strike),
            "call_oi":  call_oi,
            "put_oi":   put_oi,
            "call_chg": call_chg,   # Call OI 增減 ★
            "put_chg":  put_chg,    # Put OI 增減 ★
            "cp_ratio": round(call_oi / put_oi, 4) if put_oi > 0 else None,
        })

    # ── 找最大 OI 履約價
    max_call = max(strikes_out, key=lambda x: x["call_oi"])
    max_put  = max(strikes_out, key=lambda x: x["put_oi"])

    # ── 找 OI 增加最多的履約價（主力加碼方向）
    max_call_chg = max(strikes_out, key=lambda x: x["call_chg"])
    max_put_chg  = max(strikes_out, key=lambda x: x["put_chg"])

    record = {
        "date":          label_date,
        "near_month":    near_month,
        "week1":         week1,
        "max_call_strike": max_call["strike"],   # 最大壓力履約價
        "max_put_strike":  max_put["strike"],    # 最大支撐履約價
        "max_call_chg_strike": max_call_chg["strike"],  # Call 增加最多
        "max_put_chg_strike":  max_put_chg["strike"],   # Put 增加最多
        "strikes": strikes_out,
    }

    # 每日覆蓋 + append 歷史
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

    print(f"  ✓ 寫入成功：共 {len(strikes_out)} 個履約價")
    print(f"    最大 Call 壓力：{max_call['strike']:,}（{max_call['call_oi']:,} 口）")
    print(f"    最大 Put  支撐：{max_put['strike']:,}（{max_put['put_oi']:,} 口）")
    if prev_data:
        print(f"    Call 增加最多：{max_call_chg['strike']:,}（{max_call_chg['call_chg']:+,} 口）")
        print(f"    Put  增加最多：{max_put_chg['strike']:,}（{max_put_chg['put_chg']:+,} 口）")
    else:
        print(f"    （首日無前日資料，增減無法計算）")

def fetch_options_oi_concentration(label_date):
    """
    抓取並分析選擇權最大 OI 集中位置
    """
    print(f"▶ 額外模組：選擇權 OI 集中度分析 ({label_date})")
    
    # 這裡放您剛才在 debug7.py 寫好的分析邏輯
    # ... (省略中間的抓取與 pandas 處理過程) ...
    
    result = {
        "call_top_oi": "19800", # 假設結果
        "put_top_oi": "19400",
    }
    return result

if __name__ == "__main__":
    # 測試執行
    import datetime
    target = "2026/05/04"
    fetch_oi_strike(target, target)
