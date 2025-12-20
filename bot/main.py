#!/usr/bin/env python3
"""
Telegram Anti-Spam Bot for KryptoGO

使用 OpenAI GPT-4o-mini 智能檢測垃圾訊息
三階段處罰機制：警告 → 踢出 → 封鎖
"""

import logging
import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler as TelegramCommandHandler,
    MessageHandler as TelegramMessageHandler,
    filters
)

from bot.config import load_config
from database.db_manager import DatabaseManager
from core.spam_detector import SpamDetector
from core.punishment_manager import PunishmentManager
from core.whitelist import WhitelistManager
from utils.rate_limiter import RateLimiter
from utils.logger import setup_logger
from bot.handlers import MessageHandler
from bot.commands import CommandHandler

logger = logging.getLogger("telegram_bot")


async def initialize_bot():
    """初始化 bot 和所有元件"""
    # 載入配置
    logger.info("Loading configuration...")
    config = load_config('config.yaml')

    # 初始化資料庫
    logger.info("Initializing database...")
    db_manager = DatabaseManager('bot.db')
    await db_manager.initialize()

    # 初始化 LLM 檢測器
    logger.info("Initializing spam detector...")
    spam_detector = SpamDetector(
        openai_api_key=config['openai_api_key'],
        threshold=config['spam_threshold']
    )

    # 初始化白名單管理器
    logger.info("Initializing whitelist manager...")
    whitelist_manager = WhitelistManager('config.yaml')

    # 初始化 API 限流器
    logger.info("Initializing rate limiter...")
    rate_limiter = RateLimiter(db_manager, config['daily_api_limit'])
    await rate_limiter.initialize()

    # 建立 Telegram Bot Application
    logger.info("Building Telegram application...")
    app = Application.builder().token(config['telegram_bot_token']).build()

    # 初始化處罰管理器
    punishment_manager = PunishmentManager(db_manager, app.bot)

    # 初始化訊息處理器
    message_handler = MessageHandler(
        spam_detector=spam_detector,
        punishment_manager=punishment_manager,
        whitelist_manager=whitelist_manager,
        rate_limiter=rate_limiter,
        dry_run=config.get('dry_run', False)
    )

    # 初始化指令處理器
    command_handler = CommandHandler(
        db_manager=db_manager,
        whitelist_manager=whitelist_manager
    )

    # 註冊訊息處理器（只處理文字訊息，排除指令）
    app.add_handler(
        TelegramMessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            message_handler.handle_message
        )
    )

    # 註冊管理員指令
    app.add_handler(TelegramCommandHandler("stats", command_handler.stats_command))
    app.add_handler(TelegramCommandHandler("whitelist", command_handler.whitelist_command))
    app.add_handler(TelegramCommandHandler("reset_user", command_handler.reset_user_command))

    logger.info("Bot initialized successfully!")

    return app, whitelist_manager, config


async def post_init(application: Application, whitelist_manager: WhitelistManager, config: dict):
    """Bot 啟動後的初始化任務"""
    # 更新管理員列表
    target_chat_id = config.get('target_chat_id')
    if target_chat_id:
        try:
            await whitelist_manager.update_admin_list(application.bot, target_chat_id)
            logger.info(f"Updated admin list for chat {target_chat_id}")
        except Exception as e:
            logger.error(f"Failed to update admin list: {e}")
    else:
        logger.warning("No target_chat_id configured, admin list not updated")


def main():
    """主程式入口"""
    # 設定日誌
    config = load_config('config.yaml')
    setup_logger(config['log_file'], config['log_level'])

    logger.info("=" * 60)
    logger.info("Starting Telegram Anti-Spam Bot for KryptoGO")
    logger.info("=" * 60)

    # 建立 bot application
    app = Application.builder().token(config['telegram_bot_token']).build()

    # 初始化所有元件並註冊處理器
    async def setup_bot(application):
        # 初始化資料庫
        logger.info("Initializing database...")
        db_manager = DatabaseManager('bot.db')
        await db_manager.initialize()

        # 初始化 LLM 檢測器
        logger.info("Initializing spam detector...")
        spam_detector = SpamDetector(
            openai_api_key=config['openai_api_key'],
            threshold=config['spam_threshold']
        )

        # 初始化白名單管理器
        logger.info("Initializing whitelist manager...")
        whitelist_manager = WhitelistManager('config.yaml')

        # 初始化 API 限流器
        logger.info("Initializing rate limiter...")
        rate_limiter = RateLimiter(db_manager, config['daily_api_limit'])
        await rate_limiter.initialize()

        # 初始化處罰管理器
        punishment_manager = PunishmentManager(db_manager, app.bot)

        # 初始化訊息處理器
        message_handler = MessageHandler(
            spam_detector=spam_detector,
            punishment_manager=punishment_manager,
            whitelist_manager=whitelist_manager,
            rate_limiter=rate_limiter,
            dry_run=config.get('dry_run', False),
            enable_whitelist=config.get('enable_whitelist', True)
        )

        # 初始化指令處理器
        command_handler = CommandHandler(
            db_manager=db_manager,
            whitelist_manager=whitelist_manager
        )

        # 註冊訊息處理器
        app.add_handler(
            TelegramMessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
                message_handler.handle_message
            )
        )

        # 註冊管理員指令
        app.add_handler(TelegramCommandHandler("stats", command_handler.stats_command))
        app.add_handler(TelegramCommandHandler("whitelist", command_handler.whitelist_command))
        app.add_handler(TelegramCommandHandler("reset_user", command_handler.reset_user_command))

        logger.info("Bot initialized successfully!")

        # 啟動後初始化
        target_chat_id = config.get('target_chat_id')
        if target_chat_id:
            try:
                await whitelist_manager.update_admin_list(app.bot, target_chat_id)
                logger.info(f"Updated admin list for chat {target_chat_id}")
            except Exception as e:
                logger.error(f"Failed to update admin list: {e}")
        else:
            logger.warning("No target_chat_id configured, admin list not updated")

    # 註冊啟動時的初始化
    app.post_init = setup_bot

    try:
        # 開始輪詢
        logger.info("Bot is running... Press Ctrl+C to stop.")
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        logger.info("Received shutdown signal...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
