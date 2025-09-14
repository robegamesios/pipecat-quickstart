from __future__ import annotations

import os
from functools import lru_cache

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.moonshine.stt import MoonshineSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.daily.transport import DailyParams


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
    return KokoroTTSService(
        model_path="assets/kokoro-v1.0.onnx",
        voices_path="assets/voices-v1.0.bin",
        voice_id=voice_id,
    )


def create_llm():
    return OpenAILLMService(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY")
        )


def create_transport_params():
    vad = get_vad()
    return {
        "daily": lambda: DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=vad,
        ),
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=vad,
        ),
    }

