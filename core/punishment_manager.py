import logging
from typing import Optional, TYPE_CHECKING
from telegram import Bot, Message
from telegram.error import TelegramError

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager

logger = logging.getLogger("telegram_bot")


class PunishmentManager:
    """處罰管理器"""

    def __init__(self, db_manager: "DatabaseManager", bot: Bot):
        """
        初始化處罰管理器

        Args:
            db_manager: 資料庫管理器
            bot: Telegram Bot 實例
        """
        self.db = db_manager
        self.bot = bot
        logger.info("PunishmentManager initialized")

    async def handle_spam(self, user_id: int, username: Optional[str],
                         message: Message, llm_score: float) -> str:
        """
        處理垃圾訊息，根據違規次數執行相應處罰

        Args:
            user_id: 用戶 ID
            username: 用戶名稱
            message: 訊息物件
            llm_score: LLM 評分

        Returns:
            執行的動作 ('warning', 'kick', 'ban')
        """
        # 檢查並更新違規次數
        violation_count = await self.db.increment_violation(user_id, username)

        # 刪除垃圾訊息
        try:
            await message.delete()
            logger.info(f"Deleted spam message from user {user_id}")
        except TelegramError as e:
            logger.error(f"Failed to delete message: {e}")

        # 根據違規次數執行處罰
        if violation_count == 1:
            # 第一次：警告
            action = await self._warn_user(user_id, username, message.chat_id)

        elif violation_count == 2:
            # 第二次：踢出
            action = await self._kick_user(user_id, username, message.chat_id)

        else:  # >= 3
            # 第三次：永久封鎖
            action = await self._ban_user(user_id, username, message.chat_id)

        # 記錄到資料庫
        await self.db.log_spam(
            user_id=user_id,
            username=username,
            message_text=message.text or "",
            llm_score=llm_score,
            action=action
        )

        logger.info(
            f"Spam handled: user={user_id}, username={username}, "
            f"violation_count={violation_count}, action={action}, score={llm_score:.1f}"
        )

        return action

    async def _warn_user(self, user_id: int, username: Optional[str], chat_id: int) -> str:
        """
        發送私訊警告（靜默，不在群組通知）

        Args:
            user_id: 用戶 ID
            username: 用戶名稱
            chat_id: 群組 ID

        Returns:
            'warning'
        """
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=(
                    "⚠️ 警告：您在 KryptoGO 群組中的訊息被判定為垃圾訊息已被刪除。\n\n"
                    "這是第一次警告。再次違規將被踢出群組。\n"
                    "如有疑問，請聯繫群組管理員。"
                )
            )
            logger.info(f"Warning sent to user {user_id} ({username})")
        except TelegramError as e:
            logger.warning(f"Failed to send warning to user {user_id}: {e}")
            # 用戶可能封鎖了 bot 或關閉私訊，這不影響處罰流程

        return "warning"

    async def _kick_user(self, user_id: int, username: Optional[str], chat_id: int) -> str:
        """
        踢出用戶（可重新加入）

        Args:
            user_id: 用戶 ID
            username: 用戶名稱
            chat_id: 群組 ID

        Returns:
            'kick'
        """
        try:
            # unban_chat_member 配合 only_if_banned=False 可以踢出用戶但允許其重新加入
            await self.bot.unban_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                only_if_banned=False
            )
            logger.info(f"Kicked user {user_id} ({username}) from chat {chat_id}")

            # 嘗試發送私訊通知
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "🚫 您因多次發送垃圾訊息已被踢出 KryptoGO 群組。\n\n"
                        "這是第二次違規。您可以重新加入群組，但如再次違規將被永久封鎖。"
                    )
                )
            except TelegramError:
                pass

        except TelegramError as e:
            logger.error(f"Failed to kick user {user_id}: {e}")

        return "kick"

    async def _ban_user(self, user_id: int, username: Optional[str], chat_id: int) -> str:
        """
        永久封鎖用戶

        Args:
            user_id: 用戶 ID
            username: 用戶名稱
            chat_id: 群組 ID

        Returns:
            'ban'
        """
        try:
            await self.bot.ban_chat_member(
                chat_id=chat_id,
                user_id=user_id
            )
            logger.info(f"Banned user {user_id} ({username}) from chat {chat_id}")

            # 嘗試發送私訊通知
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "🔒 您因持續發送垃圾訊息已被永久封鎖，無法再加入 KryptoGO 群組。\n\n"
                        "如有疑問，請聯繫群組管理員。"
                    )
                )
            except TelegramError:
                pass

        except TelegramError as e:
            logger.error(f"Failed to ban user {user_id}: {e}")

        return "ban"
