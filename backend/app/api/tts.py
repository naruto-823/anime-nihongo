import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api/tts", tags=["tts"])

# 默认音色：ずんだもん（VOICEVOX speaker id 3，最有名的"基础款"动漫音色）
DEFAULT_SPEAKER = 3


class TTSBody(BaseModel):
    text: str
    speaker: int = DEFAULT_SPEAKER


def _voicevox_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        503,
        "VOICEVOX 引擎未启动或不可达。请打开 VOICEVOX.app（默认监听 50021）。"
        f" 原始错误: {exc}",
    )


@router.get("/speakers")
def list_speakers() -> list[dict]:
    """列出可用音色（VOICEVOX /speakers 透传）。"""
    try:
        r = httpx.get(f"{settings.voicevox_url}/speakers", timeout=5.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        raise _voicevox_unavailable(exc) from exc


@router.post("/synthesize")
def synthesize(body: TTSBody) -> Response:
    """文本 → WAV。两步：先 /audio_query 拿合成参数，再 /synthesis 渲染。"""
    if not body.text.strip():
        raise HTTPException(400, "text 不能为空")
    try:
        with httpx.Client(timeout=30.0) as c:
            q = c.post(
                f"{settings.voicevox_url}/audio_query",
                params={"text": body.text, "speaker": body.speaker},
            )
            q.raise_for_status()
            audio = c.post(
                f"{settings.voicevox_url}/synthesis",
                params={"speaker": body.speaker},
                json=q.json(),
                headers={"Accept": "audio/wav"},
            )
            audio.raise_for_status()
    except httpx.HTTPError as exc:
        raise _voicevox_unavailable(exc) from exc
    return Response(content=audio.content, media_type="audio/wav")
