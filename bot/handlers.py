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
        dry_run: bool = False,
        enable_whitelist: bool = True
    ):
        self.spam_detector = spam_detector
        self.punishment = punishment_manager
        self.whitelist = whitelist_manager
        self.rate_limiter = rate_limiter
        self.dry_run = dry_run
        self.enable_whitelist = enable_whitelist

        if self.dry_run:
            logger.warning("🔧 DRY RUN MODE ENABLED - No actions will be taken, only logging")
        if not self.enable_whitelist:
            logger.warning("⚠️ WHITELIST DISABLED - All messages will be checked, including admins")

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

        # Debug: 檢查訊息的回覆狀態
        logger.debug(
            f"Message reply info: "
            f"is_topic_message={message.is_topic_message}, "
            f"reply_to_message={'exists' if message.reply_to_message else 'None'}, "
            f"message_thread_id={message.message_thread_id}"
        )

        # 檢測是否回覆了不存在於本群組的訊息（跨群組回覆，常見於垃圾訊息）
        is_cross_group_reply = False

        # 情況1: reply_to_message 存在且來自不同群組
        if message.reply_to_message:
            replied_chat_id = message.reply_to_message.chat.id
            current_chat_id = message.chat.id

            if replied_chat_id != current_chat_id:
                is_cross_group_reply = True
                logger.warning(
                    f"Detected cross-group reply (case 1) from user {user_id}: "
                    f"current_chat={current_chat_id}, replied_chat={replied_chat_id}"
                )

        # 情況2: 訊息看起來像回覆但 reply_to_message 是 None（回覆不存在的訊息）
        # 檢查訊息是否有 reply_to_message_id 但沒有 reply_to_message 物件
        elif hasattr(message, 'reply_to_message_id') and message.reply_to_message_id:
            is_cross_group_reply = True
            logger.warning(
                f"Detected cross-group reply (case 2) from user {user_id}: "
                f"has reply_to_message_id={message.reply_to_message_id} but reply_to_message is None"
            )

        # 檢查白名單（如果啟用）
        if self.enable_whitelist and self.whitelist.is_whitelisted(user_id):
            logger.debug(f"User {user_id} is whitelisted, skipping check")
            return

        # 如果檢測到跨群組回覆，直接判定為垃圾訊息
        if is_cross_group_reply:
            logger.warning(f"Auto-detected spam: cross-group reply from user {user_id}")
            if self.dry_run:
                logger.warning(
                    f"🔍 [DRY RUN] Cross-group reply spam detected! user={user_id}, username={username}\n"
                    f"Message: {message_text}"
                )
            else:
                action = await self.punishment.handle_spam(
                    user_id=user_id,
                    username=username,
                    message=message,
                    llm_score=10.0  # 最高分，直接判定為垃圾訊息
                )
                logger.warning(
                    f"🚨 Cross-group reply spam! user={user_id}, username={username}, action={action}"
                )
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

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        處理群組圖片訊息（包括轉發的圖片）

        檢查流程：
        1. 檢查是否為白名單用戶
        2. 檢查 API 配額
        3. 下載圖片
        4. 使用 LLM Vision API 檢測垃圾圖片（如合約曬單）
        5. 執行相應處罰
        """
        message = update.message

        # 確保訊息有圖片
        if not message or not message.photo:
            return

        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        caption = message.caption or ""

        logger.debug(f"Processing photo from user {user_id} ({username}), caption: {caption[:50] if caption else 'No caption'}...")

        # 檢查白名單（如果啟用）
        if self.enable_whitelist and self.whitelist.is_whitelisted(user_id):
            logger.debug(f"User {user_id} is whitelisted, skipping check")
            return

        # 檢查 API 配額
        can_call = await self.rate_limiter.can_call_api()
        if not can_call:
            remaining = await self.rate_limiter.get_remaining()
            logger.warning(
                f"Daily API limit reached, skipping photo detection for user {user_id}"
            )
            if remaining == 0:
                logger.error("⚠️ API daily limit reached! No more spam detection today.")
            return

        # 下載圖片並檢測
        try:
            # 取得最大尺寸的圖片
            photo = message.photo[-1]
            photo_file = await context.bot.get_file(photo.file_id)

            # 下載圖片到記憶體
            import io
            photo_bytes = io.BytesIO()
            await photo_file.download_to_memory(photo_bytes)
            photo_data = photo_bytes.getvalue()

            # 使用 LLM Vision 檢測圖片
            is_spam, score, reasoning = await self.spam_detector.check_image(
                image_data=photo_data,
                caption=caption if caption else None
            )
            await self.rate_limiter.increment()

            logger.info(
                f"Photo checked: user={user_id}, username={username}, "
                f"score={score:.1f}, is_spam={is_spam}, reasoning={reasoning}"
            )

            # 如果是垃圾訊息，執行處罰
            if is_spam:
                if self.dry_run:
                    # Dry Run 模式：只記錄，不執行處罰
                    logger.warning(
                        f"🔍 [DRY RUN] Spam photo detected! user={user_id}, username={username}, "
                        f"score={score:.1f}, reasoning={reasoning}\n"
                        f"Caption: {caption}"
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
                        f"🚨 Spam photo detected! user={user_id}, username={username}, "
                        f"score={score:.1f}, action={action}"
                    )

        except Exception as e:
            logger.error(
                f"Error processing photo from user {user_id}: {e}",
                exc_info=True
            )
            # 錯誤時不處罰用戶，避免誤判
