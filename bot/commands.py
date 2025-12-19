import logging
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from database.db_manager import DatabaseManager
from core.whitelist import WhitelistManager

logger = logging.getLogger("telegram_bot")


class CommandHandler:
    """管理員指令處理器"""

    def __init__(self, db_manager: DatabaseManager, whitelist_manager: WhitelistManager):
        self.db = db_manager
        self.whitelist = whitelist_manager

    def is_admin(self, user_id: int) -> bool:
        """檢查用戶是否為管理員"""
        return user_id in self.whitelist.admin_ids

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /stats - 顯示統計資料

        只有管理員可以使用
        """
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            logger.warning(f"Non-admin user {user_id} tried to use /stats")
            return

        try:
            stats = await self.db.get_statistics()

            text = f"""📊 **Bot 統計資料**

**API 使用量**
今日使用：{stats['api_today']}/{stats['api_limit']}
剩餘配額：{stats['api_limit'] - stats['api_today']}

**本週統計**
檢測訊息：{stats['messages_this_week']} 則
垃圾訊息：{stats['spam_this_week']} 則
警告次數：{stats['warnings']} 次
踢出次數：{stats['kicks']} 次
封鎖次數：{stats['bans']} 次

**當前狀態**
違規用戶：{stats['active_violations']} 人
白名單用戶：{len(self.whitelist.get_whitelist())} 人
"""

            await update.message.reply_text(text, parse_mode='Markdown')
            logger.info(f"Stats sent to admin {user_id}")

        except Exception as e:
            logger.error(f"Error in stats_command: {e}", exc_info=True)
            await update.message.reply_text("❌ 取得統計資料時發生錯誤")

    async def whitelist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /whitelist - 管理白名單

        用法：
        /whitelist list - 顯示白名單
        /whitelist add <user_id> - 新增到白名單
        /whitelist remove <user_id> - 從白名單移除
        """
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            logger.warning(f"Non-admin user {user_id} tried to use /whitelist")
            return

        args = context.args

        # 沒有參數，顯示用法
        if not args:
            await update.message.reply_text(
                "**白名單管理**\n\n"
                "用法：\n"
                "`/whitelist list` - 顯示白名單\n"
                "`/whitelist add <user_id>` - 新增用戶\n"
                "`/whitelist remove <user_id>` - 移除用戶\n\n"
                "範例：`/whitelist add 123456789`",
                parse_mode='Markdown'
            )
            return

        action = args[0].lower()

        try:
            if action == "list":
                # 顯示白名單
                whitelist_users = self.whitelist.get_whitelist()
                if whitelist_users:
                    user_list = "\n".join([f"- `{uid}`" for uid in sorted(whitelist_users)])
                    text = f"**白名單用戶** ({len(whitelist_users)} 人)\n\n{user_list}"
                else:
                    text = "白名單目前是空的"

                await update.message.reply_text(text, parse_mode='Markdown')

            elif action == "add":
                # 新增到白名單
                if len(args) < 2:
                    await update.message.reply_text("❌ 請提供 user_id\n用法：`/whitelist add <user_id>`", parse_mode='Markdown')
                    return

                target_user_id = self._parse_user_id(args[1])
                if target_user_id is None:
                    await update.message.reply_text("❌ 無效的 user_id")
                    return

                success = self.whitelist.add_to_whitelist(target_user_id)
                if success:
                    await update.message.reply_text(f"✅ 已將用戶 `{target_user_id}` 加入白名單", parse_mode='Markdown')
                else:
                    await update.message.reply_text(f"⚠️ 用戶 `{target_user_id}` 已在白名單中", parse_mode='Markdown')

            elif action == "remove":
                # 從白名單移除
                if len(args) < 2:
                    await update.message.reply_text("❌ 請提供 user_id\n用法：`/whitelist remove <user_id>`", parse_mode='Markdown')
                    return

                target_user_id = self._parse_user_id(args[1])
                if target_user_id is None:
                    await update.message.reply_text("❌ 無效的 user_id")
                    return

                success = self.whitelist.remove_from_whitelist(target_user_id)
                if success:
                    await update.message.reply_text(f"✅ 已將用戶 `{target_user_id}` 從白名單移除", parse_mode='Markdown')
                else:
                    await update.message.reply_text(f"⚠️ 用戶 `{target_user_id}` 不在白名單中", parse_mode='Markdown')

            else:
                await update.message.reply_text("❌ 未知的指令。請使用 `list`, `add`, 或 `remove`", parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in whitelist_command: {e}", exc_info=True)
            await update.message.reply_text("❌ 執行指令時發生錯誤")

    async def reset_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /reset_user - 重置用戶違規記錄

        用法：/reset_user <user_id>
        """
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            logger.warning(f"Non-admin user {user_id} tried to use /reset_user")
            return

        args = context.args

        if not args:
            await update.message.reply_text(
                "用法：`/reset_user <user_id>`\n\n"
                "範例：`/reset_user 123456789`",
                parse_mode='Markdown'
            )
            return

        try:
            target_user_id = self._parse_user_id(args[0])
            if target_user_id is None:
                await update.message.reply_text("❌ 無效的 user_id")
                return

            await self.db.reset_violations(target_user_id)
            await update.message.reply_text(
                f"✅ 已重置用戶 `{target_user_id}` 的違規記錄",
                parse_mode='Markdown'
            )
            logger.info(f"Admin {user_id} reset violations for user {target_user_id}")

        except Exception as e:
            logger.error(f"Error in reset_user_command: {e}", exc_info=True)
            await update.message.reply_text("❌ 重置違規記錄時發生錯誤")

    def _parse_user_id(self, user_id_str: str) -> Optional[int]:
        """
        解析 user_id 字串

        Args:
            user_id_str: user_id 字串 (可以是純數字或 @username)

        Returns:
            user_id 或 None
        """
        try:
            # 移除 @ 符號
            if user_id_str.startswith('@'):
                # 注意：Telegram Bot API 不能直接通過 username 查詢 user_id
                # 這裡只處理純數字的情況
                return None

            return int(user_id_str)

        except ValueError:
            return None
