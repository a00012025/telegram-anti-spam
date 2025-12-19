import aiosqlite
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from database.models import Violation, SpamLog, ApiUsage

logger = logging.getLogger("telegram_bot")


class DatabaseManager:
    """資料庫管理器"""

    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """初始化資料庫，建立表格"""
        # 確保資料庫目錄存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row

        await self._create_tables()
        logger.info(f"Database initialized at {self.db_path}")

    async def _create_tables(self):
        """建立資料表"""
        async with self.connection.cursor() as cursor:
            # violations 表
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    violation_count INTEGER DEFAULT 1,
                    last_violation_time TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reset_at TIMESTAMP NOT NULL
                )
            """)

            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_id ON violations(user_id)
            """)

            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reset_at ON violations(reset_at)
            """)

            # spam_logs 表
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS spam_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    message_text TEXT,
                    llm_score REAL,
                    action TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # api_usage 表
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    count INTEGER DEFAULT 0
                )
            """)

            await self.connection.commit()

    async def get_violation(self, user_id: int) -> Optional[Violation]:
        """取得用戶的違規記錄"""
        await self._cleanup_expired_violations()

        async with self.connection.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM violations WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()

            if row:
                return Violation(
                    id=row["id"],
                    user_id=row["user_id"],
                    username=row["username"],
                    violation_count=row["violation_count"],
                    last_violation_time=datetime.fromisoformat(row["last_violation_time"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    reset_at=datetime.fromisoformat(row["reset_at"])
                )
            return None

    async def increment_violation(self, user_id: int, username: Optional[str] = None) -> int:
        """
        增加用戶違規次數

        Returns:
            當前違規次數
        """
        violation = await self.get_violation(user_id)
        now = datetime.now()
        reset_at = now + timedelta(days=30)

        async with self.connection.cursor() as cursor:
            if violation:
                # 更新現有記錄
                new_count = violation.violation_count + 1
                await cursor.execute("""
                    UPDATE violations
                    SET violation_count = ?,
                        last_violation_time = ?,
                        reset_at = ?,
                        username = ?
                    WHERE user_id = ?
                """, (new_count, now, reset_at, username, user_id))
            else:
                # 建立新記錄
                new_count = 1
                await cursor.execute("""
                    INSERT INTO violations (user_id, username, violation_count, last_violation_time, reset_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, username, new_count, now, reset_at))

            await self.connection.commit()
            logger.info(f"User {user_id} violation count: {new_count}")
            return new_count

    async def reset_violations(self, user_id: int):
        """重置用戶違規記錄"""
        async with self.connection.cursor() as cursor:
            await cursor.execute("DELETE FROM violations WHERE user_id = ?", (user_id,))
            await self.connection.commit()
            logger.info(f"Reset violations for user {user_id}")

    async def _cleanup_expired_violations(self):
        """清理過期的違規記錄"""
        async with self.connection.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM violations WHERE reset_at < ?",
                (datetime.now(),)
            )
            deleted = cursor.rowcount
            if deleted > 0:
                await self.connection.commit()
                logger.info(f"Cleaned up {deleted} expired violation records")

    async def log_spam(self, user_id: int, username: Optional[str], message_text: str,
                      llm_score: float, action: str):
        """記錄垃圾訊息日誌"""
        async with self.connection.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO spam_logs (user_id, username, message_text, llm_score, action)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, message_text, llm_score, action))
            await self.connection.commit()
            logger.debug(f"Logged spam: user={user_id}, score={llm_score}, action={action}")

    async def get_api_usage(self, date: str) -> int:
        """取得指定日期的 API 使用量"""
        async with self.connection.cursor() as cursor:
            await cursor.execute(
                "SELECT count FROM api_usage WHERE date = ?",
                (date,)
            )
            row = await cursor.fetchone()
            return row["count"] if row else 0

    async def update_api_usage(self, date: str, count: int):
        """更新 API 使用量"""
        async with self.connection.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO api_usage (date, count)
                VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET count = ?
            """, (date, count, count))
            await self.connection.commit()

    async def get_statistics(self) -> Dict[str, Any]:
        """取得統計資料"""
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        async with self.connection.cursor() as cursor:
            # 今日 API 使用量
            await cursor.execute(
                "SELECT count FROM api_usage WHERE date = ?",
                (str(today),)
            )
            row = await cursor.fetchone()
            api_today = row["count"] if row else 0

            # 本週檢測訊息數
            await cursor.execute(
                "SELECT COUNT(*) as count FROM spam_logs WHERE created_at >= ?",
                (week_ago,)
            )
            row = await cursor.fetchone()
            messages_this_week = row["count"]

            # 本週垃圾訊息數
            await cursor.execute(
                "SELECT COUNT(*) as count FROM spam_logs WHERE created_at >= ?",
                (week_ago,)
            )
            row = await cursor.fetchone()
            spam_this_week = row["count"]

            # 各類處罰次數
            await cursor.execute(
                "SELECT action, COUNT(*) as count FROM spam_logs WHERE created_at >= ? GROUP BY action",
                (week_ago,)
            )
            actions = await cursor.fetchall()
            action_counts = {row["action"]: row["count"] for row in actions}

            # 當前違規用戶數
            await cursor.execute(
                "SELECT COUNT(*) as count FROM violations WHERE reset_at > ?",
                (datetime.now(),)
            )
            row = await cursor.fetchone()
            active_violations = row["count"]

            return {
                "api_today": api_today,
                "api_limit": 1000,  # 從配置讀取
                "messages_this_week": messages_this_week,
                "spam_this_week": spam_this_week,
                "warnings": action_counts.get("warning", 0),
                "kicks": action_counts.get("kick", 0),
                "bans": action_counts.get("ban", 0),
                "active_violations": active_violations
            }

    async def close(self):
        """關閉資料庫連接"""
        if self.connection:
            await self.connection.close()
            logger.info("Database connection closed")
