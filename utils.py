import os
import json
import requests
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

def post_and_parse(session, url, payload):
    try:
        resp = session.post(url, data=payload, timeout=30)
        if resp.status_code != 200:
            return None
        return resp.text
    except Exception as e:
        print(f"  [錯誤] 請求失敗: {e}")
        return None
