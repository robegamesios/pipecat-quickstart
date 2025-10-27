from __future__ import annotations

from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    InterimTranscriptionFrame,
    OutputTransportMessageFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class UserTranscriptLogger(FrameProcessor):
    """Forwards final user transcripts to the browser chat widget.

    Emits an OutputTransportMessageFrame with type 'user_text' when a
    TranscriptionFrame arrives (skips interim frames). Passes all frames
    through unchanged.
    """

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        # Only emit for final transcripts (not interim)
        if isinstance(frame, TranscriptionFrame) and not isinstance(
            frame, InterimTranscriptionFrame
        ):
            text = getattr(frame, "text", "") or ""
            if text.strip():
                try:
                    await self.queue_frame(
                        OutputTransportMessageFrame(
                            {
                                "type": "user_text",
                                "text": str(text),
                            }
                        )
                    )
                except Exception:
                    pass

        await self.push_frame(frame, direction)
