from __future__ import annotations

from typing import List

from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TransportMessageUrgentFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class SubtitlePublisher(FrameProcessor):
    """Publishes LLM responses to the client via the transport data channel.

    Emits three app messages over the SmallWebRTC data channel:
      - {type: "subtitle_start"}
      - {type: "subtitle_delta", text: "..."} for each LLMTextFrame
      - {type: "subtitle_end", text: "..."} with the full accumulated text
    """

    def __init__(self, *, name: str | None = None):
        super().__init__(name=name or "SubtitlePublisher")
        self._buffer: List[str] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # Only react to downstream LLM frames
        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseStartFrame):
            self._buffer = []
            await self.queue_frame(TransportMessageUrgentFrame({"type": "subtitle_start"}))
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMTextFrame):
            text = getattr(frame, "text", None) or getattr(frame, "content", "")
            if text:
                self._buffer.append(text)
                await self.queue_frame(
                    TransportMessageUrgentFrame({"type": "subtitle_delta", "text": text})
                )
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            full_text = "".join(self._buffer).strip()
            await self.queue_frame(
                TransportMessageUrgentFrame({"type": "subtitle_end", "text": full_text})
            )
            await self.push_frame(frame, direction)
            return

        # Pass-through for other frames
        await self.push_frame(frame, direction)
