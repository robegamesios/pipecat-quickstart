from __future__ import annotations

import asyncio
import base64
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
    TTSSpeakFrame,
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
        # Background pre-generation TTS used only for comma-chained phrases
        self._tts_pregen = KokoroTTSService(
            model_path="assets/kokoro-v1.0.onnx",
            voices_path="assets/voices-v1.0.bin",
            voice_id=voice_id,
        )
        self._pregen_task: Optional[asyncio.Task] = None
        self._pregen_sentence: Optional[str] = None
        self._pregen_result: Optional[dict] = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, StartFrame):
            # Initialize embedded TTS and keep flowing
            await self._tts.start(frame)
            await self._tts_pregen.start(frame)
            await self.push_frame(frame, direction)
            return

        # Allow external TTSSpeakFrame to route text directly into this pipeline
        if isinstance(frame, TTSSpeakFrame):
            raw = getattr(frame, "text", None) or getattr(frame, "content", "")
            text = str(raw or "").strip()
            if text:
                # Chunk into phrases similar to streaming LLM path (split by . ! ? , ; : and ellipsis)
                import re
                parts = [p.strip() for p in re.split(r"(?<=[\.!\?\,;:\u2026])\s+", text) if p.strip()]
                if not parts:
                    parts = [text]
                for p in parts:
                    await self._queue.put(p)
                if not self._drain_task or self._drain_task.done():
                    self._drain_task = self.create_task(self._drain_queue(), name="speak-queue")
            return

        if isinstance(frame, EndFrame):
            await self._stop_drain()
            await self._stop_pregen()
            await self._tts.stop(frame)
            await self._tts_pregen.stop(frame)
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, InterruptionFrame):
            # Barge-in: stop any current speech, clear pending, reset state
            await self._stop_drain()
            await self._stop_pregen()
            await self._clear_queue()
            self._buffer = []
            self._emitted_chars = 0
            self._capturing = False
            self._last_sentence = ""
            # Hide current subtitle immediately
            await self.queue_frame(
                TransportMessageUrgentFrame({"type": "subtitle_end", "text": ""})
            )
            # Notify client to stop lipsync/audio assembly immediately
            await self.queue_frame(TransportMessageUrgentFrame({"type": "tts_interrupt"}))
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

                    # Extract completed phrases since last emission (break on ., !, ?, comma, ;, : and ellipsis)
                    pending = "".join(self._buffer)
                    slice_text = pending[self._emitted_chars :]
                    parts = re.split(r"(?<=[\.!\?\,;:\u2026])\s+", slice_text)
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
        # Speak phrases in order; update subtitles just-in-time
        # If a phrase ends with a comma, pre-generate the next phrase while speaking.
        prefetched_sentence: Optional[str] = None

        async def get_next() -> Optional[str]:
            nonlocal prefetched_sentence
            if prefetched_sentence is not None:
                s = prefetched_sentence
                prefetched_sentence = None
                return s
            if self._queue.empty():
                return None
            return await self._queue.get()

        while True:
            sentence = await get_next()
            if not sentence:
                break
            self._last_sentence = sentence
            await self.queue_frame(
                TransportMessageUrgentFrame({"type": "subtitle_delta", "text": sentence})
            )
            # Optionally launch pre-gen for the next phrase if this ends with a comma
            if sentence.rstrip().endswith(",") and self._pregen_task is None and prefetched_sentence is None and not self._queue.empty():
                try:
                    prefetched_sentence = self._queue.get_nowait()
                    self._pregen_sentence = prefetched_sentence
                    self._pregen_result = None
                    self._pregen_task = self.create_task(self._run_pregen(self._pregen_sentence), name="tts-pregen")
                except asyncio.QueueEmpty:
                    pass

            # Stream audio synchronously and measure duration; also mirror PCM over data channel
            total_frames = 0
            sample_rate = 24000

            # Announce a new phrase assembly to the client for lipsync
            sent_id = f"s-{asyncio.get_running_loop().time():.6f}".replace(".", "")
            await self.queue_frame(
                TransportMessageUrgentFrame(
                    {
                        "type": "tts_sentence_start",
                        "id": sent_id,
                        "text": sentence,
                        "sample_rate": sample_rate,
                    }
                )
            )

            # If the next phrase was pre-generated for chaining and it's exactly this sentence, use it
            if self._pregen_result is not None and self._pregen_sentence == sentence:
                frames = self._pregen_result.get("frames", [])
                sample_rate = self._pregen_result.get("sample_rate", sample_rate)
                for fr in frames:
                    out = OutputAudioRawFrame(
                        audio=fr["audio"], sample_rate=fr["sample_rate"], num_channels=fr["num_channels"]
                    )
                    await self.push_frame(out)
                    try:
                        b64 = base64.b64encode(fr["audio"]).decode("ascii")
                        await self.queue_frame(
                            TransportMessageUrgentFrame(
                                {"type": "tts_sentence_chunk", "id": sent_id, "chunk": b64}
                            )
                        )
                    except Exception:
                        pass
                # clear pregen for next cycle
                self._pregen_result = None
                self._pregen_sentence = None
                self._pregen_task = None
            else:
                async for f in self._tts.run_tts(sentence):
                    if isinstance(f, TTSAudioRawFrame):
                        sample_rate = f.sample_rate or sample_rate
                        total_frames += getattr(f, "num_frames", 0)
                        out = OutputAudioRawFrame(
                            audio=f.audio, sample_rate=f.sample_rate, num_channels=f.num_channels
                        )
                        await self.push_frame(out)
                        # Forward PCM chunk for lipsync (base64 to keep messages textual)
                        try:
                            b64 = base64.b64encode(f.audio).decode("ascii")
                            await self.queue_frame(
                                TransportMessageUrgentFrame(
                                    {
                                        "type": "tts_sentence_chunk",
                                        "id": sent_id,
                                        "chunk": b64,
                                    }
                                )
                            )
                        except Exception:
                            pass

            # Signal sentence assembly end
            await self.queue_frame(
                TransportMessageUrgentFrame({"type": "tts_sentence_end", "id": sent_id})
            )
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

    async def _stop_pregen(self):
        if self._pregen_task:
            await self.cancel_task(self._pregen_task)
            self._pregen_task = None
        self._pregen_sentence = None
        self._pregen_result = None

    async def _run_pregen(self, sentence: str):
        # Pre-generate audio frames into memory for the given sentence
        frames = []
        sample_rate = 24000
        async for f in self._tts_pregen.run_tts(sentence):
            if isinstance(f, TTSAudioRawFrame):
                sample_rate = f.sample_rate or sample_rate
                frames.append(
                    {
                        "audio": f.audio,
                        "sample_rate": f.sample_rate,
                        "num_channels": f.num_channels,
                    }
                )
        # Only store if still relevant
        if self._pregen_sentence == sentence:
            self._pregen_result = {"frames": frames, "sample_rate": sample_rate}
