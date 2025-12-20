# Telegram Anti-Spam Bot 啟動指南

## 前置準備

### 1. 建立 Telegram Bot

1. 在 Telegram 找 [@BotFather](https://t.me/botfather)
2. 發送 `/newbot` 建立新 bot
3. 按照指示設定 bot 名稱和 username
4. 取得 **Bot Token**（類似 `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）
5. 保存這個 Token，等等會用到

### 2. 取得群組 ID

1. 將你的 bot 加入目標群組
2. 在群組中發送任意訊息（例如 "test"）
3. 在瀏覽器訪問：
   ```
   https://api.telegram.org/bot<你的BOT_TOKEN>/getUpdates
   ```
   將 `<你的BOT_TOKEN>` 替換成你的 Bot Token

4. 在返回的 JSON 中找到 `"chat":{"id":-1001234567890,...}`
5. 這個負數就是你的**群組 ID**（例如 `-1001234567890`）

### 3. 設定 Bot 權限

在 Telegram 群組中：
1. 進入群組設定 → 管理員
2. 將你的 bot 提升為管理員
3. 給予以下權限：
   - ✅ 刪除訊息
   - ✅ 封鎖用戶
   - ✅ 邀請用戶

### 4. 取得 OpenAI API Key

1. 訪問 [OpenAI Platform](https://platform.openai.com/)
2. 登入並進入 API Keys 頁面
3. 點擊 "Create new secret key"
4. 保存這個 **API Key**（類似 `sk-...`）
5. 確保帳戶有餘額（建議至少充值 $5）

---

## 安裝步驟

### Step 1: 安裝 Python 依賴

```bash
# 建立虛擬環境（推薦）
python3 -m venv venv

# 啟動虛擬環境
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows

# 安裝依賴
pip install -r requirements.txt
```

### Step 2: 配置設定檔

複製範例配置檔：

```bash
cp config.yaml.example config.yaml
```

編輯 `config.yaml`，填入你的資訊：

```yaml
# Telegram Bot 設定
telegram_bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"  # 你的 Bot Token
target_chat_id: -1001234567890  # 你的群組 ID（負數）

# OpenAI 設定
openai_api_key: "sk-..."  # 你的 OpenAI API Key
spam_threshold: 8.0  # 垃圾訊息評分門檻（建議 8.0）
daily_api_limit: 1000  # 每日 API 上限

# 處罰設定
violation_reset_days: 30  # 違規記錄重置天數

# Dry Run 模式（測試用）
# 建議第一次使用先設為 true，測試一段時間後再改為 false
dry_run: true

# 白名單 (user_id 列表)
# 你可以在這裡加入不想被檢測的用戶 ID
whitelist: []

# 日誌設定
log_level: INFO
log_file: bot.log
```

### Step 3: 測試配置（可選但強烈建議）

運行測試腳本，確保 LLM 不會誤判正常訊息：

```bash
python3 test_normal_messages.py
```

預期輸出：
```
================================================================================
開始測試正常訊息檢測
垃圾訊息門檻：8.0
測試訊息數量：1
================================================================================

[1/1] 測試訊息:
  內容: 总的一个意思就是，我发ca了，能查到有没有庄...
  ✅ 正確判斷為正常訊息，評分: 3.5
  理由: 正常的交易討論和產品建議

================================================================================
測試結果統計
================================================================================
總測試數: 1
正確判斷: 1 (100.0%)
誤判數量: 0 (0.0%)

🎉 太好了！沒有誤判！
```

---

## 啟動 Bot

### 方式 1: 直接運行（測試用）

```bash
# 確保虛擬環境已啟動
source venv/bin/activate

# 啟動 bot
python3 bot/main.py
```

預期輸出：
```
============================================================
Starting Telegram Anti-Spam Bot for KryptoGO
============================================================
2025-12-20 01:30:00 - INFO - Loading configuration...
2025-12-20 01:30:00 - INFO - Initializing database...
2025-12-20 01:30:00 - INFO - Database initialized at bot.db
2025-12-20 01:30:00 - INFO - Initializing spam detector...
2025-12-20 01:30:00 - INFO - SpamDetector initialized with threshold=8.0
2025-12-20 01:30:00 - INFO - Initializing whitelist manager...
2025-12-20 01:30:00 - INFO - WhitelistManager initialized with 0 whitelisted users
2025-12-20 01:30:00 - INFO - Initializing rate limiter...
2025-12-20 01:30:00 - INFO - RateLimiter initialized with daily_limit=1000
2025-12-20 01:30:00 - INFO - RateLimiter loaded today's usage: 0/1000
2025-12-20 01:30:00 - INFO - Building Telegram application...
2025-12-20 01:30:00 - WARNING - 🔧 DRY RUN MODE ENABLED - No actions will be taken, only logging
2025-12-20 01:30:00 - INFO - Bot initialized successfully!
2025-12-20 01:30:00 - INFO - Updated admin list for chat -1001234567890
2025-12-20 01:30:00 - INFO - Bot is running... Press Ctrl+C to stop.
```

看到 `Bot is running...` 表示成功啟動！

### 方式 2: 使用 systemd（VPS 長期運行）

建立 service 檔案：

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

---

## 測試 Bot

### 1. 測試 Dry Run 模式

在群組中發送一則垃圾訊息（例如：「加我微信帶你穩賺」）

查看日誌：
```bash
tail -f bot.log | grep "DRY RUN"
```

應該會看到類似：
```
🔍 [DRY RUN] Spam detected! user=123456789, username=test_user, score=9.2, reasoning=包含私下拉人訊息
Message: 加我微信帶你穩賺
```

### 2. 測試管理員指令

在群組中發送：

```
/stats
```

應該會收到統計資料回覆：
```
📊 Bot 統計資料

API 使用量
今日使用：5/1000
剩餘配額：995

本週統計
檢測訊息：10 則
垃圾訊息：2 則
警告次數：0 次
踢出次數：0 次
封鎖次數：0 次

當前狀態
違規用戶：0 人
白名單用戶：0 人
```

### 3. 測試白名單

在群組中發送：

```
/whitelist add 123456789
```

這會將用戶 ID `123456789` 加入白名單。

---

## 正式啟用

當你測試一段時間（建議 1-2 天），確認沒有誤判後：

1. 編輯 `config.yaml`
2. 將 `dry_run: true` 改為 `dry_run: false`
3. 重啟 bot：
   ```bash
   # 如果是直接運行，按 Ctrl+C 停止，然後重新運行
   python3 bot/main.py

   # 如果是 systemd，執行
   sudo systemctl restart telegram-bot
   ```

現在 bot 會真正執行處罰動作了！

---

## 監控與維護

### 查看日誌

```bash
# 即時查看日誌
tail -f bot.log

# 只看警告和錯誤
tail -f bot.log | grep -E "WARNING|ERROR"

# 只看垃圾訊息檢測
tail -f bot.log | grep "Spam detected"
```

### 查看資料庫

```bash
sqlite3 bot.db

# 查看違規記錄
SELECT * FROM violations;

# 查看垃圾訊息日誌
SELECT * FROM spam_logs ORDER BY created_at DESC LIMIT 10;

# 查看 API 使用量
SELECT * FROM api_usage;
```

### 調整門檻值

如果發現誤判太多，可以提高門檻值：

```yaml
spam_threshold: 8.5  # 或 9.0，更嚴格
```

如果漏掉太多垃圾訊息，可以降低門檻值：

```yaml
spam_threshold: 7.5  # 更寬鬆，但可能誤判
```

---

## 常見問題

### Q: Bot 沒有反應？

1. 確認 bot 已加入群組並有管理員權限
2. 檢查 `config.yaml` 中的 `target_chat_id` 是否正確
3. 查看日誌 `bot.log` 確認錯誤訊息

### Q: 出現 "Daily API limit reached"？

- 今日 API 配額已用完，明天會自動重置
- 或者提高 `daily_api_limit`

### Q: 如何重置用戶違規記錄？

```
/reset_user 123456789
```

### Q: 如何停止 bot？

```bash
# 直接運行：按 Ctrl+C

# systemd：
sudo systemctl stop telegram-bot
```

---

## 成本預估

使用 GPT-4o-mini：
- 每則訊息約 $0.0002 - $0.0005
- 每日 1000 則上限：約 $0.20 - $0.50 / 天
- 每月約 $6 - $15

---

## 安全提醒

⚠️ **絕對不要**將以下檔案推送到 GitHub：
- `config.yaml` - 包含 API Keys
- `.env` - 環境變數
- `bot.db` - 資料庫
- `*.log` - 日誌檔案

這些已經在 `.gitignore` 中自動忽略。

---

## 取得協助

如有問題，請：
1. 查看 [README.md](README.md)
2. 檢查日誌檔案 `bot.log`
3. 在 GitHub 開 issue
