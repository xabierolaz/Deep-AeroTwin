#!/usr/bin/env python3
"""Minimal structured audit logger for zero-trust runtime analysis."""

import csv
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from constants import AUDIT_ENABLED, AUDIT_ROOT


class ZeroTrustAudit:
    def __init__(self, component: str, root_dir: Optional[str] = None):
        self.component = str(component).strip().lower() or "unknown"
        env_root = str(root_dir).strip() if root_dir is not None else str(AUDIT_ROOT).strip()
        explicit_enable = os.environ.get("PORCE_AUDIT_ENABLE")
        if explicit_enable is None:
            enabled = bool(env_root)
        else:
            enabled = bool(AUDIT_ENABLED)

        self.enabled = bool(enabled and env_root)
        self.root_dir: Optional[Path] = Path(env_root) if env_root else None
        self.component_dir: Optional[Path] = None
        self.frames_dir: Optional[Path] = None
        self.events_path: Optional[Path] = None
        self._events_fp = None
        self._csv_ready: set[str] = set()
        self._lock = threading.Lock()

        if not self.enabled:
            return

        try:
            assert self.root_dir is not None
            self.root_dir.mkdir(parents=True, exist_ok=True)
            self.component_dir = self.root_dir / self.component
            self.component_dir.mkdir(parents=True, exist_ok=True)
            self.frames_dir = self.component_dir / "frames"
            self.frames_dir.mkdir(parents=True, exist_ok=True)
            self.events_path = self.component_dir / "events.jsonl"
            self._events_fp = self.events_path.open("a", encoding="utf-8", buffering=1)
            self.log_event(
                "audit_component_start",
                component=self.component,
                pid=int(os.getpid()),
                cwd=str(Path.cwd()),
            )
        except Exception:
            self.enabled = False
            self._close_silent()

    @staticmethod
    def _iso_utc_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    def log_event(self, kind: str, **fields: Any) -> None:
        if not self.enabled or self._events_fp is None:
            return
        rec = {
            "ts": float(time.time()),
            "iso_utc": self._iso_utc_now(),
            "kind": str(kind),
        }
        rec.update(fields)
        try:
            line = json.dumps(rec, ensure_ascii=False)
        except Exception:
            return
        with self._lock:
            try:
                self._events_fp.write(line + "\n")
                self._events_fp.flush()
            except Exception:
                pass

    def save_frame(
        self,
        *,
        frame_index: int,
        image_bgr: Any,
        prefix: str = "frame",
        jpeg_quality: int = 90,
    ) -> Optional[str]:
        if not self.enabled or self.frames_dir is None:
            return None
        try:
            import cv2  # local import to keep this module lightweight for non-vision processes
        except Exception:
            return None

        filename = f"{str(prefix)}_{int(frame_index):06d}.jpg"
        out_path = self.frames_dir / filename
        ok = False
        try:
            ok = bool(
                cv2.imwrite(
                    str(out_path),
                    image_bgr,
                    [int(cv2.IMWRITE_JPEG_QUALITY), int(max(1, min(100, jpeg_quality)))],
                )
            )
        except Exception:
            ok = False
        return str(out_path) if ok else None

    def init_csv(self, filename: str, headers: Iterable[str]) -> Optional[str]:
        if not self.enabled or self.component_dir is None:
            return None
        name = str(filename).strip()
        if not name:
            return None
        out_path = self.component_dir / name
        hdr = [str(h) for h in headers]
        with self._lock:
            if name in self._csv_ready:
                return str(out_path)
            needs_header = not out_path.exists() or out_path.stat().st_size == 0
            if needs_header:
                with out_path.open("w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=hdr)
                    w.writeheader()
            self._csv_ready.add(name)
        return str(out_path)

    def append_csv_row(self, filename: str, headers: Iterable[str], row: Mapping[str, Any]) -> None:
        if not self.enabled or self.component_dir is None:
            return
        name = str(filename).strip()
        if not name:
            return
        hdr = [str(h) for h in headers]
        out_path = self.component_dir / name
        self.init_csv(name, hdr)
        data = {h: row.get(h, "") for h in hdr}
        with self._lock:
            try:
                with out_path.open("a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=hdr)
                    w.writerow(data)
            except Exception:
                pass

    def _close_silent(self) -> None:
        try:
            if self._events_fp is not None:
                self._events_fp.close()
        except Exception:
            pass
        self._events_fp = None

    def close(self) -> None:
        if self.enabled:
            self.log_event("audit_component_stop", component=self.component)
        self._close_silent()
