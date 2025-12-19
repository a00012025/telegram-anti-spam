# Telegram Anti-Spam Bot for KryptoGO

智能垃圾訊息檢測機器人，使用 OpenAI GPT-4o-mini 為 KryptoGO 加密貨幣交易討論群提供自動化管理。

## 功能特色

- **智能檢測**：使用 GPT-4o-mini 分析訊息內容，理解交易討論群特性
- **三階段處罰**：警告 → 踢出 → 永久封鎖
- **白名單保護**：管理員和指定用戶免於檢測
- **成本控制**：每日 API 呼叫上限 1000 次
- **違規管理**：自動記錄違規歷史，30 天後重置
- **統計功能**：查看檢測統計和 API 使用量
- **靜默處理**：不在群組公開通知，私訊警告用戶

## 快速開始

### 1. 安裝依賴

```bash
# 建立虛擬環境（推薦）
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或 venv\Scripts\activate  # Windows

# 安裝依賴
pip install -r requirements.txt
```

### 2. 配置設定

複製 `.env.example` 為 `.env` 並填入你的 API 金鑰：

```bash
cp .env.example .env
```

編輯 `.env`：

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
```

編輯 `config.yaml`：

```yaml
# 填入你的群組 ID（負數）
target_chat_id: -1001234567890

# 調整垃圾訊息評分門檻（0-10，預設 8.0）
spam_threshold: 8.0

# 每日 API 呼叫上限
daily_api_limit: 1000

# 白名單用戶 ID 列表
whitelist:
  - 123456789
  - 987654321
```

### 3. 取得必要資訊

**Telegram Bot Token：**
1. 在 Telegram 找 [@BotFather](https://t.me/botfather)
2. 發送 `/newbot` 建立新 bot
3. 取得 Bot Token

**群組 ID：**
1. 將 bot 加入你的群組
2. 發送任意訊息到群組
3. 訪問 `https://api.telegram.org/bot<你的BOT_TOKEN>/getUpdates`
4. 找到 `chat.id`（負數）

**OpenAI API Key：**
1. 訪問 [OpenAI Platform](https://platform.openai.com/)
2. 建立 API Key

### 4. 設定 Bot 權限

在 Telegram 群組中，給予 bot 以下權限：
- ✅ 刪除訊息
- ✅ 封鎖用戶
- ✅ 邀請用戶（踢出後重新加入）

### 5. 啟動 Bot

```bash
python3 bot/main.py
```

或使用 systemd 在 VPS 上長期運行（見下方）。

## 管理員指令

所有指令只有群組管理員可以使用。

### `/stats` - 查看統計資料

顯示 bot 運行統計：
- 今日 API 使用量
- 本週檢測訊息數
- 本週垃圾訊息數
- 警告/踢出/封鎖次數
- 當前違規用戶數

### `/whitelist` - 管理白名單

```bash
# 顯示白名單
/whitelist list

# 新增用戶到白名單
/whitelist add 123456789

# 從白名單移除用戶
/whitelist remove 123456789
```

### `/reset_user` - 重置違規記錄

```bash
# 重置用戶的違規記錄
/reset_user 123456789
```

## 工作原理

### 檢測流程

1. **訊息過濾**
   - 忽略白名單用戶（管理員 + 配置的白名單）
   - 忽略指令訊息
   - 只檢測群組文字訊息

2. **API 配額檢查**
   - 檢查今日是否還有 API 配額
   - 達到上限後停止檢測，隔日自動重置

3. **LLM 檢測**
   - 使用 GPT-4o-mini 分析訊息
   - 給出 0-10 分評分
   - ≥8 分判定為垃圾訊息

4. **執行處罰**
   - 第 1 次：刪除訊息 + 私訊警告
   - 第 2 次：踢出群組（可重新加入）
   - 第 3 次：永久封鎖

### 垃圾訊息定義

針對加密貨幣交易討論群，以下行為被視為垃圾訊息：

- ❌ 私下拉人（「加我 LINE」「私聊帶單」）
- ❌ 過度推銷（「包賺不賠」「保證獲利」）
- ❌ 無關廣告（賣產品、其他服務）
- ❌ 惡意洗版、騷擾

正常交易討論**不會**被判定為垃圾：

- ✅ 分享交易策略和技術分析
- ✅ 討論 BTC/ETH 價格走勢
- ✅ 討論止盈止損點位
- ✅ 分享交易心得

## 專案結構

```
telegram-admin-helper/
├── bot/
│   ├── main.py           # 主程式入口
│   ├── handlers.py       # 訊息處理器
│   ├── commands.py       # 管理員指令
│   └── config.py         # 配置載入
├── core/
│   ├── spam_detector.py  # LLM 垃圾檢測
│   ├── punishment_manager.py  # 處罰管理
│   └── whitelist.py      # 白名單管理
├── database/
│   ├── models.py         # 資料模型
│   └── db_manager.py     # 資料庫操作
├── utils/
│   ├── logger.py         # 日誌設定
│   └── rate_limiter.py   # API 限流
├── config.yaml           # 配置檔案
├── requirements.txt      # Python 依賴
└── README.md            # 本檔案
```

## VPS 部署（systemd）

建立 systemd service 檔案：

```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

內容：

```ini
[Unit]
Description=Telegram Anti-Spam Bot for KryptoGO
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/telegram-admin-helper
Environment="PATH=/path/to/telegram-admin-helper/venv/bin"
ExecStart=/path/to/telegram-admin-helper/venv/bin/python3 bot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

啟動服務：

```bash
# 重載 systemd
sudo systemctl daemon-reload

# 啟動 bot
sudo systemctl start telegram-bot

# 設定開機自動啟動
sudo systemctl enable telegram-bot

# 查看狀態
sudo systemctl status telegram-bot

# 查看日誌
sudo journalctl -u telegram-bot -f
```

## 日誌

日誌會同時輸出到：
- 檔案：`bot.log`（自動輪替，保留 5 個檔案，每個 10MB）
- 控制台：標準輸出

日誌級別可在 `config.yaml` 中調整（DEBUG, INFO, WARNING, ERROR）。

## 資料庫

使用 SQLite 儲存：
- 違規記錄（30 天後自動清理）
- 垃圾訊息日誌
- API 使用量記錄

資料庫檔案：`bot.db`

## 成本估算

使用 GPT-4o-mini：
- 輸入：$0.150 / 1M tokens
- 輸出：$0.600 / 1M tokens

預估每則訊息檢測成本：約 $0.0002 - $0.0005

每日 1000 則上限：約 $0.20 - $0.50 / 天

## 常見問題

### Q: Bot 沒有反應？

1. 確認 bot 已加入群組並有管理員權限
2. 檢查 `config.yaml` 中的 `target_chat_id` 是否正確
3. 查看日誌 `bot.log` 確認錯誤訊息

### Q: 如何調整檢測嚴格程度？

編輯 `config.yaml` 中的 `spam_threshold`：
- `7.0` - 較嚴格（可能誤判）
- `8.0` - 平衡（推薦）
- `9.0` - 較寬鬆（只抓明顯的垃圾）

### Q: 如何增加 API 配額？

編輯 `config.yaml` 中的 `daily_api_limit`，但注意成本會相應增加。

### Q: 違規記錄多久會重置？

預設 30 天，可在 `config.yaml` 中調整 `violation_reset_days`。

### Q: 如何查看今日還有多少 API 配額？

使用 `/stats` 指令查看。

## 授權

本專案為私人使用，請勿用於商業用途。

## 支援

如有問題，請聯繫專案維護者。
