import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(log_file: str = "bot.log", log_level: str = "INFO") -> logging.Logger:
    """
    設定日誌系統

    Args:
        log_file: 日誌檔案路徑
        log_level: 日誌級別 (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        配置好的 Logger 實例
    """
    logger = logging.getLogger("telegram_bot")
    logger.setLevel(getattr(logging, log_level.upper()))

    # 避免重複添加 handler
    if logger.handlers:
        return logger

    # 確保日誌目錄存在
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 檔案處理器（自動輪替，最多保留 5 個檔案，每個 10MB）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    # 控制台處理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    ))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
