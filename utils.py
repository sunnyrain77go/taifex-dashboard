import os
import json
import requests
import pandas as pd
from io import StringIO
from config import DATA_DIR, HEADERS

def load_json(filepath):
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_json(filepath, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def already_exists(filepath, date_label):
    records = load_json(filepath)
    if isinstance(records, list):
        return any(r.get("date") == date_label for r in records)
    return records.get("date") == date_label

def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://www.taifex.com.tw/cht/3/futContractsDate", timeout=15)
    except Exception:
        pass
    return s

def flatten_cols(df):
    df.columns = [
        "_".join(str(x).strip() for x in col) if isinstance(col, tuple) else str(col).strip()
        for col in df.columns
    ]
    return df

def post_and_parse(session, url, payload):
    try:
        resp = session.post(url, data=payload, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return pd.read_html(StringIO(resp.text))
    except Exception as e:
        print(f"  [錯誤] 請求或解析失敗: {e}")
        return None
