"""语音合成：基于 edge-tts（免费，微软 Edge 音色）。"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import edge_tts


def _synth(text: str, voice: str, rate: str, volume: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(communicate.save(str(out_path)))
    finally:
        loop.close()


def synthesize(
    text: str,
    voice: str = "zh-CN-XiaoxiaoNeural",
    rate: str = "+0%",
    volume: str = "+0%",
    out_dir: str | Path | None = None,
) -> Path:
    """合成语音到 mp3 文件并返回路径。"""
    out_dir = Path(out_dir) if out_dir else Path(tempfile.gettempdir()) / "nanami_tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"tts_{abs(hash(text))}.mp3"
    _synth(text, voice, rate, volume, out_path)
    return out_path
