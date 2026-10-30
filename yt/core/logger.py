# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class ProjectStatus:
    project_id: str
    topic: str
    phase: str = "pending"
    progress: int = 0
    error: str | None = None
    script: str | None = None
    audio_path: str | None = None
    video_path: str | None = None
    video_paths: dict | None = None
    render_params: dict | None = None
    voice_settings: dict | None = None
    run_mode: str = "semi"
    scenes: list | None = None
    post: dict | None = None
    review_reasons: list | None = None
    clips_folder: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    logs: list = field(default_factory=list, repr=False)

    def log(self, msg: str, level: str = "info"):
        self.logs.append({"t": time.time(), "msg": msg, "level": level})

    def update(self, phase: str, progress: int, **kwargs):
        self.phase = phase
        self.progress = progress
        self.updated_at = time.time()
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self._save_to_disk()

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "topic": self.topic,
            "phase": self.phase,
            "progress": self.progress,
            "error": self.error,
            "script": self.script,
            "audio_path": self.audio_path,
            "video_path": self.video_path,
            "video_paths": self.video_paths,
            "render_params": self.render_params,
            "voice_settings": self.voice_settings,
            "run_mode": self.run_mode,
            "scenes": self.scenes,
            "post": self.post,
            "review_reasons": self.review_reasons,
            "clips_folder": self.clips_folder,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def _save_to_disk(self):
        path = os.path.join("projects", self.project_id, "status.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectStatus":
        return cls(
            project_id=d["project_id"],
            topic=d.get("topic", ""),
            phase=d.get("phase", "done"),
            progress=d.get("progress", 100),
            error=d.get("error"),
            script=d.get("script"),
            audio_path=d.get("audio_path"),
            video_path=d.get("video_path"),
            video_paths=d.get("video_paths"),
            render_params=d.get("render_params"),
            voice_settings=d.get("voice_settings"),
            run_mode=d.get("run_mode", "semi"),
            scenes=d.get("scenes"),
            post=d.get("post"),
            review_reasons=d.get("review_reasons"),
            clips_folder=d.get("clips_folder"),
            created_at=d.get("created_at", 0),
            updated_at=d.get("updated_at", 0),
        )
