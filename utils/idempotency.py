"""
幂等性辅助工具，可用于避免重复写入
目前预留，可根据需要扩展（如基于 Redis 或数据库记录已处理 ID）
"""
from typing import Set
from pathlib import Path
import pickle


class SimpleIdempotencyStore:
    """基于本地文件的简易幂等记录（仅用于小规模演示）"""

    def __init__(self, file_path: str = ".idempotency_cache.pkl"):
        self.file_path = Path(file_path)
        self.seen_ids: Set[str] = set()
        self._load()

    def _load(self):
        if self.file_path.exists():
            with open(self.file_path, "rb") as f:
                self.seen_ids = pickle.load(f)

    def _save(self):
        with open(self.file_path, "wb") as f:
            pickle.dump(self.seen_ids, f)

    def is_processed(self, record_id: str) -> bool:
        return record_id in self.seen_ids

    def mark_processed(self, record_id: str):
        self.seen_ids.add(record_id)
        self._save()

    def clear(self):
        self.seen_ids.clear()
        self._save()