import yaml
import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
import logging

logger = logging.getLogger("telegram_bot")


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    載入配置檔案

    優先順序：
    1. 環境變數 (.env)
    2. 配置檔案 (config.yaml)

    Args:
        config_path: 配置檔案路徑

    Returns:
        配置字典
    """
    # 載入 .env 檔案
    load_dotenv()

    # 讀取 config.yaml
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 環境變數覆蓋配置檔案
    config['telegram_bot_token'] = os.getenv('TELEGRAM_BOT_TOKEN', config.get('telegram_bot_token'))
    config['openai_api_key'] = os.getenv('OPENAI_API_KEY', config.get('openai_api_key'))

    # 驗證必要配置
    required_keys = ['telegram_bot_token', 'openai_api_key']
    missing_keys = [key for key in required_keys if not config.get(key)]

    if missing_keys:
        raise ValueError(f"Missing required config keys: {missing_keys}")

    # 設定預設值
    config.setdefault('spam_threshold', 8.0)
    config.setdefault('daily_api_limit', 1000)
    config.setdefault('violation_reset_days', 30)
    config.setdefault('log_level', 'INFO')
    config.setdefault('log_file', 'bot.log')
    config.setdefault('whitelist', [])

    logger.info(f"Config loaded from {config_path}")
    return config
