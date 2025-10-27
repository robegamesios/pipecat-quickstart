from __future__ import annotations

import json
from typing import Any, Dict

from pipecat.frames.frames import (
    Frame,
    FunctionCallInProgressFrame,
    FunctionCallResultFrame,
    FunctionCallsStartedFrame,
    OutputTransportMessageFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class ToolUsageLogger(FrameProcessor):
    """Forwards tool usage events to the browser over the data channel.

    Emits OutputTransportMessageFrame messages with type 'log_tool'. The
    front-end (injected script) prints them with console.error so they remain
    visible even when non-error logs are suppressed.
    """

    def __init__(self, *, name: str | None = None):
        super().__init__(name=name or "ToolUsageLogger")
        self._tool_seen_in_turn: bool = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, OutputTransportMessageFrame):
            msg = getattr(frame, "message", {}) or {}
            typ = msg.get("type")
            if typ == "subtitle_end":
                # Spoken turn ends; if no tools were used, mark LLM-only
                if not self._tool_seen_in_turn:
                    await self.queue_frame(
                        OutputTransportMessageFrame(
                            {"type": "log_tool", "phase": "llm_only", "name": "llm"}
                        )
                    )
                # reset for next turn
                self._tool_seen_in_turn = False
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, FunctionCallsStartedFrame):
            self._tool_seen_in_turn = True
            for call in frame.function_calls:
                payload = {
                    "type": "log_tool",
                    "phase": "started",
                    "name": getattr(call, "function_name", "unknown"),
                    "args": _safe_trim(getattr(call, "arguments", {})),
                }
                await self.queue_frame(OutputTransportMessageFrame(payload))
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, FunctionCallInProgressFrame):
            self._tool_seen_in_turn = True
            payload = {
                "type": "log_tool",
                "phase": "in_progress",
                "name": frame.function_name,
                "args": _safe_trim(frame.arguments),
            }
            await self.queue_frame(OutputTransportMessageFrame(payload))
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, FunctionCallResultFrame):
            self._tool_seen_in_turn = True
            payload = {
                "type": "log_tool",
                "phase": "result",
                "name": frame.function_name,
                "args": _safe_trim(frame.arguments),
            }
            await self.queue_frame(OutputTransportMessageFrame(payload))
            await self.push_frame(frame, direction)
            return

        # Default pass-through for other frames

        await self.push_frame(frame, direction)


def _safe_trim(obj: Dict[str, Any] | None) -> Dict[str, Any]:
    if not obj:
        return {}
    try:
        text = json.dumps(obj)
        if len(text) > 300:
            text = text[:297] + "..."
        return {"preview": text}
    except Exception:
        return {}
