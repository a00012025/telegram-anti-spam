from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Violation:
    """違規記錄"""
    id: Optional[int]
    user_id: int
    username: Optional[str]
    violation_count: int
    last_violation_time: datetime
    created_at: datetime
    reset_at: datetime  # 30天後的重置時間


@dataclass
class SpamLog:
    """垃圾訊息日誌"""
    id: Optional[int]
    user_id: int
    username: Optional[str]
    message_text: str
    llm_score: float
    action: str  # 'warning', 'kick', 'ban'
    created_at: datetime


@dataclass
class ApiUsage:
    """API 使用量記錄"""
    id: Optional[int]
    date: str  # YYYY-MM-DD
    count: int
