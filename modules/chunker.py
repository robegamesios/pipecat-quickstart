from __future__ import annotations

import re
from typing import List

from pipecat.frames.frames import (
    Frame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class SentenceChunker(FrameProcessor):
    """Collects full LLM response, chunks by sentence, and feeds TTS + subtitles.

    - Swallows streaming LLMTextFrame tokens so TTS doesn't speak prematurely.
    - On LLM end, splits the accumulated text into sentences.
    - For each sentence: emits a subtitle message and a TTSSpeakFrame.
    """

    def __init__(self, *, name: str | None = None):
        super().__init__(name=name or "SentenceChunker")
        self._buffer: List[str] = []
        self._capturing = False
        self._emitted_chars: int = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseStartFrame):
            # Start capturing tokens for this response
            self._buffer = []
            self._capturing = True
            self._emitted_chars = 0
            # Keep passing the start frame downstream for metrics/observers
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMTextFrame):
            if self._capturing:
                text = getattr(frame, "text", None) or getattr(frame, "content", "")
                if text:
                    self._buffer.append(text)

                    # Streaming sentence extraction: emit as soon as a sentence completes
                    pending = "".join(self._buffer)
                    # Look for completed sentences after last emission
                    slice_text = pending[self._emitted_chars :]
                    # Split by sentence boundaries, keeping punctuation
                    parts = re.split(r"(?<=[.!?])\s+", slice_text)
                    # All but the last part are complete sentences
                    complete = parts[:-1]
                    for sent in complete:
                        s = sent.strip()
                        if s:
                            # Speak queued sentence; subtitles will update after TTS
                            await self.queue_frame(TTSSpeakFrame(s))
                            self._emitted_chars += len(sent) + 1  # +1 for the space we split on
            # Swallow LLMTextFrame to prevent immediate TTS from tokens
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            self._capturing = False
            full_text = "".join(self._buffer)
            # Emit any trailing text as the final sentence
            trailing = full_text[self._emitted_chars :].strip()
            if trailing:
                await self.queue_frame(TTSSpeakFrame(trailing))

            # Pass the end frame downstream
            await self.push_frame(frame, direction)
            return

        # Pass-through for other frames
        await self.push_frame(frame, direction)
