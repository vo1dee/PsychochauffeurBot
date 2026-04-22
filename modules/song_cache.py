import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CAP = 1000


class SongCache:
    """Persistent mapping of YouTube video_id → Telegram audio file_id."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            logger.info(f"SongCache: no existing cache at {self._path}")
            return
        try:
            with open(self._path, encoding='utf-8') as f:
                self._data = json.load(f)
            logger.info(f"SongCache: loaded {len(self._data)} entries")
        except Exception as e:
            logger.warning(f"SongCache: load failed ({e}), starting empty")
            self._data = {}

    def get(self, video_id: str) -> Optional[dict]:
        return self._data.get(video_id)

    def set(self, video_id: str, file_id: str, title: str, performer: Optional[str],
            webpage_url: str, duration: Optional[int] = None) -> None:
        self._data[video_id] = {
            'file_id': file_id,
            'title': title,
            'performer': performer,
            'webpage_url': webpage_url,
            'duration': duration,
            'stored_at': datetime.utcnow().isoformat(),
        }
        if len(self._data) > _CAP:
            oldest = sorted(self._data.items(), key=lambda x: x[1].get('stored_at', ''))
            for old_id, _ in oldest[:len(self._data) - _CAP]:
                del self._data[old_id]
        self._save()

    def evict(self, video_id: str) -> None:
        if video_id in self._data:
            del self._data[video_id]
            self._save()
            logger.info(f"SongCache: evicted stale entry {video_id}")

    def _save(self) -> None:
        tmp = str(self._path) + '.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False)
            os.replace(tmp, self._path)
        except Exception as e:
            logger.error(f"SongCache: save failed: {e}")
