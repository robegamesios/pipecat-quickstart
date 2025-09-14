"""Custom FastAPI server to run the Pipecat bot and mount the ADA2 avatar UI.

This server:
- Exposes the Small WebRTC signalling endpoint at `/api/offer`.
- Mounts the prebuilt Pipecat small WebRTC UI at `/client`.
- Mounts the ADA2 avatar client (Three.js TalkingHead) at `/ada2`.

Usage:
  uv run server_ada2.py --host localhost --port 7860

Override the ADA2 client path with env var `ADA2_CLIENT_PATH` if needed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from pipecat.runner.types import SmallWebRTCRunnerArguments
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection


def create_app(ada2_client_path: str) -> FastAPI:
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount prebuilt Pipecat small WebRTC UI
    try:
        from pipecat_ai_small_webrtc_prebuilt.frontend import SmallWebRTCPrebuiltUI

        app.mount("/client", SmallWebRTCPrebuiltUI)
    except Exception as e:
        logger.error(f"Could not mount prebuilt UI: {e}")

    # Mount ADA2 avatar client assets
    if not os.path.isdir(ada2_client_path):
        logger.warning(
            f"ADA2 client path not found: {ada2_client_path}. Set ADA2_CLIENT_PATH to override."
        )
    else:
        app.mount("/ada2", StaticFiles(directory=ada2_client_path, html=True), name="ada2")
        logger.info(f"Mounted ADA2 client at /ada2 from {ada2_client_path}")

        def _inject_subtitle_script(html: str) -> str:
            # Ensure relative paths resolve against /ada2/
            if "<base" not in html:
                html = html.replace("<head>", "<head>\n<base href=\"/ada2/\">\n")

            injection = (
                "<script>\n"
                "(function(){\n"
                "  const OrigPC = window.RTCPeerConnection;\n"
                "  if(!OrigPC) return;\n"
                "  function attachChannel(ch){\n"
                "    if(!ch) return;\n"
                "    ch.onopen = () => { try { ch.send('ping-' + Date.now()); } catch(e){};\n"
                "      if(!window.__pcPing){ window.__pcPing = setInterval(()=>{ try{ ch.send('ping-' + Date.now()) }catch(e){} }, 1000);}\n"
                "    };\n"
                "    ch.onclose = () => { if(window.__pcPing){ clearInterval(window.__pcPing); window.__pcPing=null; } };\n"
                "    ch.onmessage = (ev) => {\n"
                "      try{ const msg = JSON.parse(ev.data);\n"
                "        const box = (function(){ let el = document.getElementById('subtitles'); if(!el){ el = document.createElement('div'); el.id='subtitles'; el.style.cssText='position:fixed;bottom:100px;left:50%;transform:translateX(-50%);max-width:70vw;background:rgba(0,0,0,0.6);padding:8px 12px;border-radius:10px;font-size:18px;line-height:1.3;text-align:center;z-index:200;color:#fff;'; document.body.appendChild(el);} return el; })();\n"
                "        if(msg.type==='subtitle_start'){ box.textContent=''; box.style.display='block'; }\n"
                "        else if(msg.type==='subtitle_delta'){ box.textContent += (msg.text||''); box.style.display='block'; }\n"
                "        else if(msg.type==='subtitle_end'){ box.textContent = (msg.text||''); box.style.display = (box.textContent?'block':'none'); }\n"
                "      }catch(e){}\n"
                "    };\n"
                "  }\n"
                "  window.RTCPeerConnection = function(cfg){ const pc = new OrigPC(cfg); try{ const dc = pc.createDataChannel('app', {ordered:true}); attachChannel(dc); }catch(e){} pc.addEventListener('datachannel', (ev)=> attachChannel(ev.channel)); return pc; };\n"
                "  window.RTCPeerConnection.prototype = OrigPC.prototype;\n"
                "})();\n"
                "</script>\n"
            )
            if '</body>' in html:
                return html.replace('</body>', injection + '</body>')
            return html + injection

        @app.get("/ada2-ui", include_in_schema=False)
        async def ada2_ui_root():
            try:
                index_path = os.path.join(ada2_client_path, "index.html")
                with open(index_path, "r", encoding="utf-8") as f:
                    html = f.read()
                return HTMLResponse(_inject_subtitle_script(html))
            except Exception as e:
                logger.error(f"Failed to read ADA2 index.html: {e}")
                return RedirectResponse(url="/ada2/index.html")

        @app.get("/ada2-ui/", include_in_schema=False)
        async def ada2_ui_index():
            return await ada2_ui_root()

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/ada2-ui/")

    # Manage active peer connections by pc_id
    pcs_map: Dict[str, SmallWebRTCConnection] = {}

    @app.post("/api/offer")
    async def offer(request: dict, background_tasks: BackgroundTasks):
        pc_id = request.get("pc_id")

        if pc_id and pc_id in pcs_map:
            connection = pcs_map[pc_id]
            await connection.renegotiate(
                sdp=request["sdp"], type=request.get("type", "offer"), restart_pc=request.get("restart_pc", False)
            )
        else:
            connection = SmallWebRTCConnection()
            await connection.initialize(sdp=request["sdp"], type=request.get("type", "offer"))

            @connection.event_handler("closed")
            async def on_closed(conn: SmallWebRTCConnection):
                pcs_map.pop(conn.pc_id, None)

            # Import local bot and start it as a background task
            import bot as bot_module

            runner_args = SmallWebRTCRunnerArguments(webrtc_connection=connection)
            background_tasks.add_task(bot_module.bot, runner_args)

        answer = connection.get_answer()
        pcs_map[answer["pc_id"]] = connection
        return answer

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        # Ensure all peer connections are cleaned up on shutdown
        await asyncio.gather(*[pc.disconnect() for pc in pcs_map.values()])
        pcs_map.clear()

    app.router.lifespan_context = lifespan
    return app


def main():
    parser = argparse.ArgumentParser(description="Pipecat + ADA2 server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument(
        "--ada2-path",
        default=os.getenv("ADA2_CLIENT_PATH", "/Users/robenriquez/Documents/00_Github/ADA2/pipecat-client"),
        help="Path to ADA2/pipecat-client directory",
    )
    args = parser.parse_args()

    app = create_app(args.ada2_path)

    import uvicorn

    logger.info(
        f"Server ready. Open http://{args.host}:{args.port}/ada2-ui/ to use the ADA2 avatar client."
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
