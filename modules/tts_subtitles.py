from __future__ import annotations

from pipecat.frames.frames import TTSTextFrame
from pipecat.services.kokoro.tts import KokoroTTSService


class KokoroTTSWithSubtitles(KokoroTTSService):
    """Kokoro TTS that emits TTSTextFrame before audio for subtitle sync."""

    async def _push_tts_frames(self, text: str):  # type: ignore[override]
        # Emit the sentence upfront to align UI with spoken audio
        await self.push_frame(TTSTextFrame(text))

        # Temporarily disable trailing TTSTextFrame from base implementation
        original_push_text = getattr(self, "_push_text_frames", False)
        try:
            setattr(self, "_push_text_frames", False)
            await super()._push_tts_frames(text)
        finally:
            setattr(self, "_push_text_frames", original_push_text)

