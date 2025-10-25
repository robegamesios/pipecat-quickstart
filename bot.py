#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Pipecat Quickstart Example.

The example runs a simple voice AI bot that you can connect to using your
browser and speak with it. You can also deploy this bot to Pipecat Cloud.

Required AI services:
- Moonshine (Local Speech-to-Text)
- OpenAI (LLM)
- Kokoro (Local Text-to-Speech)

Run the bot using::

    uv run bot.py
"""

import os
from typing import List, cast
from datetime import datetime

from dotenv import load_dotenv
from openai.types.chat import ChatCompletionMessageParam
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import BaseTransport

from modules.services import (
    create_llm,
    create_stt,
    create_tts,
    create_transport_params,
)
from modules.tools import (
    create_all_tools,
    register_weather_tool,
    register_google_search_tool,
    register_book_tools,
)
from modules.tool_logger import ToolUsageLogger
from modules.sentence_tts import SentenceTTSPipeline
from modules.tts_bridge import register_speaker, unregister_speaker
from modules.chat_bridge import register_sender, unregister_sender
from modules.interrupt_bridge import register_interrupter, unregister_interrupter
from modules.user_transcript_logger import UserTranscriptLogger
from pipecat.audio.vad.vad_analyzer import VADParams
from modules.session_store import (
    get_history,
    set_history,
    get_session,
    set_session,
    summarize_and_trim,
    was_cleared,
)

load_dotenv(override=True)

# Global mode; 'chat' or 'reader'
BOT_MODE = os.getenv("PIPELINE_MODE", "chat").strip().lower()
# Stable client identity (set by server per /api/offer)
CLIENT_ID = None


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    stt = create_stt()
    # TTS is owned by SentenceTTSPipeline; keep factory here for future use if needed
    llm = create_llm()
    # Register tool-call handlers (weather + google search)
    register_weather_tool(llm)
    register_google_search_tool(llm)
    register_book_tools(llm)

    # Prompt for gpt-4o, gpt-4o-mini
    base_messages: List[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": (
                "You are a friendly, thoughtful AI assistant. "
                "If this is the user's very first message in the conversation, greet them warmly. "
                "Otherwise, continue the conversation naturally without repeating a greeting. "
                "Keep answers clear and conversational, using a warm and approachable tone. "
                "Be concise unless more detail is requested, and avoid sounding robotic or overly formal. "
                "Always add value to your responses rather than just restating the user's message. "
                "When asked about weather, call the get_current_weather tool with location and unit, "
                "and include a 'when' argument like 'now', 'tomorrow morning', or 'tonight' when applicable. "
                "When asked for recent or factual information from the web, use the google_search tool first and summarize the top results clearly. "
                "Write in plain text only, no Markdown, no asterisks, no bullet symbols or tables. Do not include URLs; cite sources by outlet name only. "
                "When summarizing search results, write around five sentences per item, using clear, complete sentences. "
                "Do not number or bullet the items; separate items with a blank line. "
                "When you present results, say 'degrees Fahrenheit' or 'degrees Celsius' explicitly and spell wind units out: "
                "use 'miles per hour' when using Fahrenheit and 'kilometers per hour' when using Celsius. "
                "For books: prefer tools to handle all commands. For example: 'list books' → book_list; '"
                "'focus on book 1' → book_focus; 'list chapters' → book_list_chapters; 'read chapter 3' → book_read_chapter; '"
                "'next section' → book_next_chapter; 'previous section' → book_previous_chapter. If uncertain, call book_command_router with the raw text. "
                "When reading a section, return only the raw section text so the system may speak it. Do not paraphrase the content."
            ),
        },
    ]

    # Restore conversation summary + recent turns for this client if available
    cid = globals().get("CLIENT_ID")
    summary, turns = ("", [])
    try:
        summary, turns = get_session(cid)
        if not summary and not turns:
            legacy = get_history(cid)
            if legacy:
                turns = [m for m in legacy if m.get("role") in ("user", "assistant")]
                set_session(cid, "", turns)
    except Exception:
        summary, turns = "", []

    messages: List[ChatCompletionMessageParam] = list(base_messages)
    # Inject current system date/time for the assistant to use in responses
    try:
        now = datetime.now().astimezone()
        now_str = now.strftime("%A, %B %d, %Y %I:%M %p %Z")
        messages.append(
            cast(ChatCompletionMessageParam, {
                "role": "system",
                "content": f"Current date and time: {now_str}",
            })
        )
    except Exception:
        pass
    if summary:
        messages.append(
            cast(
                ChatCompletionMessageParam,
                {"role": "system", "content": f"Conversation Summary (for context):\n{summary}"},
            )
        )
    for m in turns:
        r = str(m.get("role", ""))
        if r in ("user", "assistant"):
            messages.append(
                cast(
                    ChatCompletionMessageParam,
                    {"role": r, "content": str(m.get("content", ""))},
                )
            )

    # Provide tools to the context so the model may call them.
    context = OpenAILLMContext(messages, tools=create_all_tools(), tool_choice="auto")
    context_aggregator = llm.create_context_aggregator(context)

    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

    # Collect full LLM response, chunk by sentence, feed TTS + subtitles
    # Allow voice selection via env var KOKORO_VOICE_ID (default: af_sarah)
    voice_id = os.getenv("KOKORO_VOICE_ID", "af_sarah")
    sentence_tts = SentenceTTSPipeline(voice_id=voice_id)
    tool_logger = ToolUsageLogger()

    pipeline = Pipeline(
        [
            transport.input(),
            rtvi,
            stt,
            UserTranscriptLogger(),
            context_aggregator.user(),
            llm,
            sentence_tts,
            tool_logger,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[RTVIObserver(rtvi)],
    )

    # Track whether we restored prior history
    had_history = bool(summary or turns)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Relax VAD slightly on first connect to avoid missing first short utterance
        try:
            from modules.services import get_vad
            get_vad().set_params(VADParams(confidence=0.6, start_secs=0.12, stop_secs=0.6, min_volume=0.35))
        except Exception:
            pass
        # Register a speaker function for external chapter reading
        # Register a speaker function for external chapter reading
        try:
            pc_id = (
                getattr(getattr(transport, "connection", None), "pc_id", None)
                or getattr(getattr(runner_args, "webrtc_connection", None), "pc_id", None)
                or "default"
            )
            async def _speak(text: str):
                from pipecat.frames.frames import TTSSpeakFrame  # local import to avoid top-level deps
                await task.queue_frames([TTSSpeakFrame(text)])

            register_speaker(str(pc_id), _speak)
            async def _send(text: str):
                # Append a user message and trigger the LLM on the same pipeline
                messages.append({"role": "user", "content": str(text)})
                await task.queue_frames([LLMRunFrame()])

            register_sender(str(pc_id), _send)

            # Register an interrupter that injects an InterruptionFrame into this session's pipeline
            from pipecat.frames.frames import InterruptionFrame

            async def _interrupt():
                await task.queue_frames([InterruptionFrame()])

            register_interrupter(str(pc_id), _interrupt)
        except Exception:
            pass
        # Kick off a greeting only when starting fresh in chat mode
        if BOT_MODE != "reader" and not had_history:
            messages.append({"role": "system", "content": "Say Hello, I'm ADA. How can I assist you today?"})
            await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        try:
            pc_id = (
                getattr(getattr(transport, "connection", None), "pc_id", None)
                or getattr(getattr(runner_args, "webrtc_connection", None), "pc_id", None)
                or "default"
            )
            unregister_speaker(str(pc_id))
            unregister_sender(str(pc_id))
            unregister_interrupter(str(pc_id))
            # Persist user/assistant turns + summarize oldest unless cleared
            try:
                cid = globals().get("CLIENT_ID")
                if cid and not was_cleared(cid):
                    # Convert to simple role/content dicts for summarization
                    all_turns = [
                        {
                            "role": str(m.get("role", "")),
                            "content": str(m.get("content", "")),
                        }
                        for m in messages
                        if m.get("role") in ("user", "assistant")
                    ]
                    summary_now, kept = summarize_and_trim(cid, all_turns, keep_last=30, summarize_chunk=30, max_summary_chars=3500)
                    set_session(cid, summary_now, kept)
            except Exception:
                pass
        except Exception:
            pass
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)

    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Main bot entry point for the bot starter."""

    transport = await create_transport(runner_args, create_transport_params())

    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
