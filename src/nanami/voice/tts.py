"""语音合成：多后端可切换（edge-tts / http / cosyvoice）。"""
from __future__ import annotations

import asyncio
import json
import tempfile
import urllib.request
from pathlib import Path

import edge_tts

from ..config import resolve_api_key

_COSYVOICE_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"


def _synth_edge(text: str, voice: str, rate: str, volume: str, pitch: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(communicate.save(str(out_path)))
    finally:
        loop.close()


def _synth_http(text: str, url: str, out_path: Path) -> None:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        out_path.write_bytes(resp.read())


def _synth_cosyvoice(
    text: str, model: str, voice: str, api_key: str, fmt: str, sample_rate: int, out_path: Path
) -> None:
    payload = json.dumps(
        {
            "model": model,
            "input": {
                "text": text,
                "voice": voice,
                "format": fmt,
                "sample_rate": sample_rate,
            },
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        _COSYVOICE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    audio = (result.get("output") or {}).get("audio") or {}
    audio_url = audio.get("url")
    if not audio_url:
        raise RuntimeError(f"CosyVoice 合成失败：{result}")
    with urllib.request.urlopen(audio_url) as resp:
        out_path.write_bytes(resp.read())


def synthesize(
    text: str,
    *,
    provider: str = "edge",
    voice: str = "zh-CN-XiaoxiaoNeural",
    rate: str = "+0%",
    volume: str = "+0%",
    pitch: str = "+0Hz",
    http: dict | None = None,
    cosyvoice: dict | None = None,
    out_dir: str | Path | None = None,
) -> Path:
    """合成语音到音频文件并返回路径。provider: edge | http | cosyvoice。"""
    out_dir = Path(out_dir) if out_dir else Path(tempfile.gettempdir()) / "nanami_tts"
    out_dir.mkdir(parents=True, exist_ok=True)

    if provider == "edge":
        out_path = out_dir / f"tts_{abs(hash(text + provider + voice))}.mp3"
        _synth_edge(text, voice, rate, volume, pitch, out_path)
        return out_path

    if provider == "http":
        http = http or {}
        url = http["url"]
        ext = http.get("out_format", "wav").lstrip(".")
        out_path = out_dir / f"tts_{abs(hash(text + provider + url))}{'.' + ext}"
        _synth_http(text, url, out_path)
        return out_path

    if provider == "cosyvoice":
        cosyvoice = cosyvoice or {}
        model = cosyvoice["model"]
        vid = cosyvoice["voice"]
        api_key = resolve_api_key(
            {"api_key_env": cosyvoice.get("api_key_env", "DASHSCOPE_API_KEY")}
        )
        fmt = cosyvoice.get("format", "mp3")
        sample_rate = cosyvoice.get("sample_rate", 24000)
        out_path = out_dir / f"tts_{abs(hash(text + provider + vid))}.{fmt}"
        _synth_cosyvoice(text, model, vid, api_key, fmt, sample_rate, out_path)
        return out_path

    raise ValueError(f"未知的 TTS provider: {provider}")
