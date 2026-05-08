# Taifex Dashboard (台股籌碼分析工具)

這是一個自動化抓取並分析台灣期交所 (Taifex) 與證交所 (TWSE) 籌碼資料的工具集。主要用於追蹤外資部位、選擇權未平倉量 (OI) 分佈，並產出結構化的 JSON 數據、Excel 報表，甚至同步至 Google Sheets。

## 🌟 主要功能

1. **自動化數據抓取**：
   - **期貨部位**：外資台指期貨淨未平倉口數與金額。
   - **選擇權部位**：外資選擇權 Call/Put 未平倉口數與金額，並計算淨部位趨勢。
   - **P/C Ratio**：全市場 Put/Call Ratio 未平倉比率（核心多空指標）。
   - **現貨買賣超**：三大法人（外資、投信、自營商）現貨買賣超數據與外資近五日累計。
2. **深度選擇權分析 (`options_analysis.py`)**：
   - **合約識別**：自動從混雜的 CSV 數據中識別出最接近的「週選 (Weekly)」與「月選 (Monthly)」合約。
   - **分佈統計**：分析壓力區（Call OI 最大值）與支撐區（Put OI 最大值）。
   - **動態訊號**：根據週月選支撐壓力的對比，產出「短多長空」、「多頭一致」等即時籌碼訊號。
3. **數據整合與匯出 (`export_data.py`)**：
   - 所有數據以 JSON 格式持久化儲存於 `data/`。
   - 一鍵匯出為 **Excel (`taifex_summary.xlsx`)**，包含所有模組的彙整。
   - 支援同步至 **Google Sheets** (需設定 API 憑證與 Sheet ID)。
4. **AI 分析助手 (`gen_prompt.py`)**：
   - 快速生成專為 AI (如 ChatGPT/Claude) 設計的 Prompt，將繁雜的籌碼數據轉化為易讀的分析報告。

## 📂 專案結構

- `fetch_taifex.py`: 主要進入點，執行期貨、選擇權與 P/C Ratio 的抓取。
- `fetch_stock_net.py`: 抓取證交所三大法人現貨買賣超數據。
- `options_analysis.py`: 核心分析邏輯，處理 OI 分佈、契約篩選與訊號生成。
- `export_data.py`: 資料匯出模組，將 JSON 轉換為 Excel 或雲端試算表。
- `utils.py` / `config.py`: 底層工具函式與路徑設定。
- `data/`: 歷史數據庫，包含 `futures.json`, `options_pc.json`, `pc_ratio.json`, `oi_strike.json`, `stock_net.json`。

## 🚀 快速開始

### 1. 安裝環境
確保您的環境已安裝 Python 3.8+，並安裝所需套件：
```bash
pip install pandas requests openpyxl gspread oauth2client
```

### 2. 執行每日數據抓取
預設會抓取今日（或最新交易日）的資料：
```bash
python fetch_taifex.py
```

### 3. 抓取特定歷史日期
若要補抓或分析過去某天的資料，可直接帶入日期參數：
```bash
python fetch_taifex.py 2026/05/07
```

### 4. 匯出彙整報表
```bash
python export_data.py
```
*提示：加上 `--sheets` 參數可同步更新至 Google Sheets。*

## 📊 資料格式
數據統一儲存於 `data/` 下，採用標準 JSON 格式，方便與其他系統介接或進行二次開發。

## 🛠️ 進階自定義
- **調整 Headers**: 若遇到阻擋，可在 `config.py` 修改 `HEADERS`。
- **修改分析條件**: 可在 `options_analysis.py` 修改 `build_strikes` 或 `gen_signal` 以符合個人策略。

---
*免責聲明：本工具提供的所有數據與分析僅供研究與參考，不構成任何形式的投資建議。*
