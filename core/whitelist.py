import logging
import yaml
from pathlib import Path
from typing import Set
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger("telegram_bot")


class WhitelistManager:
    """白名單管理器"""

    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化白名單管理器

        Args:
            config_path: 配置檔案路徑
        """
        self.config_path = Path(config_path)
        self.whitelist: Set[int] = set()
        self.admin_ids: Set[int] = set()
        self._load_whitelist()
        logger.info(f"WhitelistManager initialized with {len(self.whitelist)} whitelisted users")

    def _load_whitelist(self):
        """從配置檔案載入白名單"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    whitelist_data = config.get('whitelist', [])
                    self.whitelist = set(whitelist_data) if whitelist_data else set()
                    logger.info(f"Loaded {len(self.whitelist)} users from whitelist")
            else:
                logger.warning(f"Config file not found: {self.config_path}")
                self.whitelist = set()
        except Exception as e:
            logger.error(f"Failed to load whitelist: {e}", exc_info=True)
            self.whitelist = set()

    def _save_whitelist(self):
        """儲存白名單到配置檔案"""
        try:
            # 讀取現有配置
            config = {}
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}

            # 更新白名單
            config['whitelist'] = sorted(list(self.whitelist))

            # 寫回檔案
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

            logger.info(f"Saved {len(self.whitelist)} users to whitelist")

        except Exception as e:
            logger.error(f"Failed to save whitelist: {e}", exc_info=True)

    def is_whitelisted(self, user_id: int) -> bool:
        """
        檢查用戶是否在白名單

        Args:
            user_id: 用戶 ID

        Returns:
            True 如果用戶在白名單或是管理員
        """
        return user_id in self.whitelist or user_id in self.admin_ids

    async def update_admin_list(self, bot: Bot, chat_id: int):
        """
        從 Telegram 取得群組管理員列表並更新

        Args:
            bot: Telegram Bot 實例
            chat_id: 群組 ID
        """
        try:
            admins = await bot.get_chat_administrators(chat_id)
            self.admin_ids = {admin.user.id for admin in admins}
            logger.info(f"Updated admin list: {len(self.admin_ids)} admins")
        except TelegramError as e:
            logger.error(f"Failed to get admin list: {e}")

    def add_to_whitelist(self, user_id: int) -> bool:
        """
        新增用戶到白名單

        Args:
            user_id: 用戶 ID

        Returns:
            True 如果成功新增，False 如果用戶已在白名單
        """
        if user_id in self.whitelist:
            logger.info(f"User {user_id} already in whitelist")
            return False

        self.whitelist.add(user_id)
        self._save_whitelist()
        logger.info(f"Added user {user_id} to whitelist")
        return True

    def remove_from_whitelist(self, user_id: int) -> bool:
        """
        從白名單移除用戶

        Args:
            user_id: 用戶 ID

        Returns:
            True 如果成功移除，False 如果用戶不在白名單
        """
        if user_id not in self.whitelist:
            logger.info(f"User {user_id} not in whitelist")
            return False

        self.whitelist.discard(user_id)
        self._save_whitelist()
        logger.info(f"Removed user {user_id} from whitelist")
        return True

    def get_whitelist(self) -> Set[int]:
        """取得白名單用戶列表"""
        return self.whitelist.copy()

    def get_all_protected_users(self) -> Set[int]:
        """取得所有受保護的用戶（白名單 + 管理員）"""
        return self.whitelist | self.admin_ids
