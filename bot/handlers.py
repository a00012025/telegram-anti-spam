import logging
from telegram import Update
from telegram.ext import ContextTypes

from core.spam_detector import SpamDetector
from core.punishment_manager import PunishmentManager
from core.whitelist import WhitelistManager
from utils.rate_limiter import RateLimiter

logger = logging.getLogger("telegram_bot")


class MessageHandler:
    """訊息處理器"""

    def __init__(
        self,
        spam_detector: SpamDetector,
        punishment_manager: PunishmentManager,
        whitelist_manager: WhitelistManager,
        rate_limiter: RateLimiter,
        dry_run: bool = False
    ):
        self.spam_detector = spam_detector
        self.punishment = punishment_manager
        self.whitelist = whitelist_manager
        self.rate_limiter = rate_limiter
        self.dry_run = dry_run

        if self.dry_run:
            logger.warning("🔧 DRY RUN MODE ENABLED - No actions will be taken, only logging")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        處理群組訊息

        檢查流程：
        1. 檢查是否為白名單用戶
        2. 檢查 API 配額
        3. 使用 LLM 檢測垃圾訊息
        4. 執行相應處罰
        """
        message = update.message

        # 忽略非文字訊息
        if not message or not message.text:
            return

        # 忽略指令
        if message.text.startswith('/'):
            return

        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        message_text = message.text

        logger.debug(f"Processing message from user {user_id} ({username}): {message_text[:50]}...")

        # 檢查白名單
        if self.whitelist.is_whitelisted(user_id):
            logger.debug(f"User {user_id} is whitelisted, skipping check")
            return

        # 檢查 API 配額
        can_call = await self.rate_limiter.can_call_api()
        if not can_call:
            remaining = await self.rate_limiter.get_remaining()
            logger.warning(
                f"Daily API limit reached, skipping detection for message from user {user_id}"
            )
            # 達到上限後不檢測，但記錄日誌
            if remaining == 0:
                # 只在第一次達到上限時記錄
                logger.error("⚠️ API daily limit reached! No more spam detection today.")
            return

        # 使用 LLM 檢測垃圾訊息
        try:
            is_spam, score, reasoning = await self.spam_detector.check_message(message_text)
            await self.rate_limiter.increment()

            logger.info(
                f"Message checked: user={user_id}, username={username}, "
                f"score={score:.1f}, is_spam={is_spam}, reasoning={reasoning}"
            )

            # 如果是垃圾訊息，執行處罰
            if is_spam:
                if self.dry_run:
                    # Dry Run 模式：只記錄，不執行處罰
                    logger.warning(
                        f"🔍 [DRY RUN] Spam detected! user={user_id}, username={username}, "
                        f"score={score:.1f}, reasoning={reasoning}\n"
                        f"Message: {message_text}"
                    )
                else:
                    # 正常模式：執行處罰
                    action = await self.punishment.handle_spam(
                        user_id=user_id,
                        username=username,
                        message=message,
                        llm_score=score
                    )
                    logger.warning(
                        f"🚨 Spam detected! user={user_id}, username={username}, "
                        f"score={score:.1f}, action={action}"
                    )

        except Exception as e:
            logger.error(
                f"Error processing message from user {user_id}: {e}",
                exc_info=True
            )
            # 錯誤時不處罰用戶，避免誤判
