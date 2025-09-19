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
from typing import List

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
)
from modules.tool_logger import ToolUsageLogger
from modules.sentence_tts import SentenceTTSPipeline

load_dotenv(override=True)


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    stt = create_stt()
    # TTS is owned by SentenceTTSPipeline; keep factory here for future use if needed
    llm = create_llm()
    # Register tool-call handlers (weather + google search)
    register_weather_tool(llm)
    register_google_search_tool(llm)

    # Prompt for gpt-4o, gpt-4o-mini
    messages: List[ChatCompletionMessageParam] = [
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
                "use 'miles per hour' when using Fahrenheit and 'kilometers per hour' when using Celsius."
            ),
        },
    ]

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

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Kick off the conversation.
        messages.append({"role": "system", "content": "Say hello and briefly introduce yourself."})
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
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
