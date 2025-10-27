from __future__ import annotations

import os
from typing import Optional
from functools import lru_cache

from pipecat.audio.vad.silero import SileroVADAnalyzer
from .tts_subtitles import KokoroTTSWithSubtitles
from pipecat.services.moonshine.stt import MoonshineSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams


@lru_cache(maxsize=1)
def get_vad() -> SileroVADAnalyzer:
    return SileroVADAnalyzer()


def create_stt():
    return MoonshineSTTService(
        model_name="moonshine/tiny",
        language=Language.EN,
        vad_enabled=True,
        vad_analyzer=get_vad(),
    )


def create_tts(voice_id: str = "af_sarah"):
    return KokoroTTSWithSubtitles(
        model_path="assets/kokoro-v1.0.onnx",
        voices_path="assets/voices-v1.0.bin",
        voice_id=voice_id,
    )


def require_env(name: str, default: Optional[str] = None) -> str:
    """Fetch a required environment variable as a plain string.

    Provides an optional default to keep type as `str` (not Optional) and
    raises a clear error if the variable is missing and no default is given.
    """
    val = os.getenv(name)
    if val is None or val == "":
        if default is not None:
            return default
        raise RuntimeError(f"Missing environment variable: {name}")
    return val


def create_llm():
    return OpenAILLMService(
        model=require_env("OPENAI_MODEL", default="gpt-4o-mini"),
        api_key=require_env("OPENAI_API_KEY"),
    )


def create_transport_params():
    vad = get_vad()
    # Single built-in transport (SmallWebRTC)
    return {
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=vad,
        ),
    }
