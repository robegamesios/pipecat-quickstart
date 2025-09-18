from __future__ import annotations

from pipecat.frames.frames import (
    Frame,
    TTSTextFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TransportMessageUrgentFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class SubtitlesAfterTTS(FrameProcessor):
    """Converts TTS frames into subtitle app-messages.

    Place this AFTER TTS so we emit subtitles exactly when audio starts.
    """

    def __init__(self, *, name: str | None = None):
        super().__init__(name=name or "SubtitlesAfterTTS")
        self._last_text: str = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TTSStartedFrame):
            await self.queue_frame(TransportMessageUrgentFrame({"type": "subtitle_start"}))
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TTSTextFrame):
            self._last_text = getattr(frame, "text", "")
            await self.queue_frame(
                TransportMessageUrgentFrame({"type": "subtitle_delta", "text": self._last_text})
            )
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TTSStoppedFrame):
            await self.queue_frame(
                TransportMessageUrgentFrame({"type": "subtitle_end", "text": self._last_text})
            )
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

