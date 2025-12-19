import logging
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager

logger = logging.getLogger("telegram_bot")


class RateLimiter:
    """API 使用量限流器"""

    def __init__(self, db_manager: "DatabaseManager", daily_limit: int = 1000):
        """
        初始化限流器

        Args:
            db_manager: 資料庫管理器
            daily_limit: 每日 API 呼叫上限
        """
        self.db = db_manager
        self.daily_limit = daily_limit
        self._today = date.today()
        self._count = 0
        self._initialized = False
        logger.info(f"RateLimiter initialized with daily_limit={daily_limit}")

    async def initialize(self):
        """初始化限流器，載入今日使用量"""
        await self._refresh_if_new_day()
        self._initialized = True
        logger.info(f"RateLimiter loaded today's usage: {self._count}/{self.daily_limit}")

    async def can_call_api(self) -> bool:
        """
        檢查今日是否還能呼叫 API

        Returns:
            True 如果還有配額，False 如果已達上限
        """
        if not self._initialized:
            await self.initialize()

        await self._refresh_if_new_day()
        can_call = self._count < self.daily_limit

        if not can_call:
            logger.warning(f"Daily API limit reached: {self._count}/{self.daily_limit}")

        return can_call

    async def increment(self):
        """增加 API 呼叫計數"""
        if not self._initialized:
            await self.initialize()

        self._count += 1
        await self.db.update_api_usage(str(self._today), self._count)
        logger.debug(f"API usage incremented: {self._count}/{self.daily_limit}")

    async def get_remaining(self) -> int:
        """取得今日剩餘配額"""
        if not self._initialized:
            await self.initialize()

        await self._refresh_if_new_day()
        return max(0, self.daily_limit - self._count)

    async def get_usage(self) -> tuple[int, int]:
        """
        取得今日使用量

        Returns:
            (current_count, daily_limit)
        """
        if not self._initialized:
            await self.initialize()

        await self._refresh_if_new_day()
        return (self._count, self.daily_limit)

    async def _refresh_if_new_day(self):
        """檢查是否跨日，如果是則重置計數"""
        today = date.today()
        if today != self._today:
            self._today = today
            self._count = await self.db.get_api_usage(str(today))
            logger.info(f"New day detected, reset API counter: {self._count}/{self.daily_limit}")
