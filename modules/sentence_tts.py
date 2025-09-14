from __future__ import annotations

import asyncio
import re
from typing import List, Optional

from pipecat.frames.frames import (
    EndFrame,
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    OutputAudioRawFrame,
    StartFrame,
    TTSAudioRawFrame,
    TransportMessageUrgentFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.kokoro.tts import KokoroTTSService


class SentenceTTSPipeline(FrameProcessor):
    """Owns sentence chunking + TTS + subtitles to keep them in lockstep.

    Place this directly after the LLM in the pipeline. Do not add a separate
    TTS processor; this node streams audio frames itself.
    """

    def __init__(self, *, name: Optional[str] = None, voice_id: str = "af_sarah"):
        super().__init__(name=name or "SentenceTTSPipeline")
        self._buffer: List[str] = []
        self._emitted_chars: int = 0
        self._capturing: bool = False
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._drain_task: Optional[asyncio.Task] = None
        self._last_sentence: str = ""

        # Embedded TTS service
        self._tts = KokoroTTSService(
            model_path="assets/kokoro-v1.0.onnx",
            voices_path="assets/voices-v1.0.bin",
            voice_id=voice_id,
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, StartFrame):
            # Initialize embedded TTS and keep flowing
            await self._tts.start(frame)
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, EndFrame):
            await self._stop_drain()
            await self._tts.stop(frame)
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, InterruptionFrame):
            # Barge-in: stop any current speech, clear pending, reset state
            await self._stop_drain()
            await self._clear_queue()
            self._buffer = []
            self._emitted_chars = 0
            self._capturing = False
            self._last_sentence = ""
            # Hide current subtitle immediately
            await self.queue_frame(
                TransportMessageUrgentFrame({"type": "subtitle_end", "text": ""})
            )
            # Propagate interruption downstream so transports can react
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMFullResponseStartFrame):
            self._buffer = []
            self._emitted_chars = 0
            self._capturing = True
            self._last_sentence = ""
            # Signal UI we're starting a spoken response
            await self.queue_frame(TransportMessageUrgentFrame({"type": "subtitle_start"}))
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMTextFrame):
            if self._capturing:
                text = getattr(frame, "text", None) or getattr(frame, "content", "")
                if text:
                    self._buffer.append(text)

                    # Extract completed sentences since last emission
                    pending = "".join(self._buffer)
                    slice_text = pending[self._emitted_chars :]
                    parts = re.split(r"(?<=[.!?])\s+", slice_text)
                    for sent in parts[:-1]:
                        s = sent.strip()
                        if s:
                            await self._queue.put(s)
                            self._emitted_chars += len(sent) + 1

                    # Start drainer if needed
                    if not self._drain_task or self._drain_task.done():
                        self._drain_task = self.create_task(self._drain_queue(), name="speak-queue")
            # Swallow token frames to avoid speaking mid-sentence
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            self._capturing = False
            pending = "".join(self._buffer)
            trailing = pending[self._emitted_chars :].strip()
            if trailing:
                await self._queue.put(trailing)
            if not self._drain_task or self._drain_task.done():
                self._drain_task = self.create_task(self._drain_queue(), name="speak-queue")
            await self.push_frame(frame, direction)
            return

        # Pass-through anything else
        await self.push_frame(frame, direction)

    async def _drain_queue(self):
        # Speak sentences in order; update subtitles just-in-time
        while not self._queue.empty():
            sentence = await self._queue.get()
            self._last_sentence = sentence
            await self.queue_frame(
                TransportMessageUrgentFrame({"type": "subtitle_delta", "text": sentence})
            )
            # Stream audio synchronously and measure duration to pace subtitle advance
            total_frames = 0
            sample_rate = 24000
            async for f in self._tts.run_tts(sentence):
                if isinstance(f, TTSAudioRawFrame):
                    sample_rate = f.sample_rate or sample_rate
                    total_frames += getattr(f, "num_frames", 0)
                    out = OutputAudioRawFrame(
                        audio=f.audio, sample_rate=f.sample_rate, num_channels=f.num_channels
                    )
                    await self.push_frame(out)
            # Approximate playout time to hold subtitle until audio finishes
            duration_s = (total_frames / max(sample_rate, 1)) if total_frames else max(len(sentence) * 0.06, 0.4)
            await asyncio.sleep(duration_s + 0.05)
            self._queue.task_done()

        # Keep last sentence visible until next start
        await self.queue_frame(
            TransportMessageUrgentFrame({"type": "subtitle_end", "text": self._last_sentence})
        )

    async def _stop_drain(self):
        if self._drain_task:
            await self.cancel_task(self._drain_task)
            self._drain_task = None

    async def _clear_queue(self):
        try:
            while not self._queue.empty():
                self._queue.get_nowait()
                self._queue.task_done()
        except Exception:
            pass
