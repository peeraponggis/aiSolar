# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

"""A persistent queue of topics, rendered one at a time in fully automatic mode.

One at a time because each clip uses the whole GPU (voice clone / AI images)
and CPU (render). Items survive a server restart; one that was running starts
again as a new project.
"""
import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Awaitable, Callable

STATUSES = ("waiting", "running", "needs_review", "done", "error")


class ClipQueue:
    def __init__(self, path: Path, run_item: Callable[[dict], Awaitable[str]], projects: dict):
        self.path = path
        self.run_item = run_item          # starts the clip, waits for it, returns project_id
        self.projects = projects          # project_id -> ProjectStatus
        self.paused = False
        self._wake = asyncio.Event()
        self.items: list[dict] = []
        if path.exists():
            self.items = json.loads(path.read_text(encoding="utf-8"))
        for item in self.items:
            if item["status"] == "running":
                item.update(status="waiting", project_id=None)
        self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.items, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def snapshot(self) -> dict:
        items = []
        for item in self.items:
            view = {k: v for k, v in item.items() if k != "settings"}
            status = self.projects.get(item.get("project_id") or "")
            if status and item["status"] == "running":
                view["progress"] = status.progress
                view["phase"] = status.phase
            items.append(view)
        return {"paused": self.paused, "items": items}

    def add(self, settings: dict) -> dict:
        item = {"id": uuid.uuid4().hex[:8], "topic": settings["topic"], "settings": settings,
                "status": "waiting", "project_id": None, "error": None,
                "added_at": time.time(), "finished_at": None}
        self.items.append(item)
        self._save()
        self._wake.set()
        return item

    def remove(self, item_id: str) -> bool:
        before = len(self.items)
        self.items = [i for i in self.items if not (i["id"] == item_id and i["status"] != "running")]
        self._save()
        return len(self.items) < before

    def retry(self, item_id: str) -> bool:
        for item in self.items:
            if item["id"] == item_id and item["status"] in ("error", "needs_review"):
                item.update(status="waiting", project_id=None, error=None, finished_at=None)
                self._save()
                self._wake.set()
                return True
        return False

    def clear_finished(self):
        self.items = [i for i in self.items if i["status"] in ("waiting", "running")]
        self._save()

    def set_paused(self, paused: bool):
        self.paused = paused
        self._wake.set()

    async def worker(self):
        while True:
            item = None if self.paused else next((i for i in self.items if i["status"] == "waiting"), None)
            if not item:
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass
                continue
            item.update(status="running", started_at=time.time())
            self._save()
            try:
                project_id = await self.run_item(item)
                item["project_id"] = project_id
                status = self.projects[project_id]
                if status.phase == "done":
                    item["status"] = "done"
                elif status.phase == "media_ready":
                    item["status"] = "needs_review"
                    item["error"] = "; ".join(status.review_reasons or [])[:300]
                else:
                    item["status"] = "error"
                    item["error"] = (status.error or "").strip().split("\n")[-1][:300]
            except Exception as e:
                item.update(status="error", error=str(e)[:300])
            item["finished_at"] = time.time()
            self._save()
