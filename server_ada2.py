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

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
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
        # Serve ADA2 static assets under /ada2-static (no direct UI at /ada2)
        app.mount("/ada2-static", StaticFiles(directory=ada2_client_path, html=False), name="ada2_static")
        logger.info(f"Mounted ADA2 static assets at /ada2-static from {ada2_client_path}")

        # Optionally mount an external ADA2 frontend/public tree for exact UI files
        ada2_ui_public_path = os.getenv("ADA2_UI_PUBLIC_PATH", "").strip()
        js_base = "/ada2-static"
        if ada2_ui_public_path and os.path.isdir(ada2_ui_public_path):
            try:
                app.mount("/ada2-ext", StaticFiles(directory=ada2_ui_public_path, html=False), name="ada2_ext")
                js_base = "/ada2-ext"
                logger.info(f"Mounted external ADA2 UI at /ada2-ext from {ada2_ui_public_path}")
            except Exception as e:
                logger.warning(f"Could not mount ADA2_UI_PUBLIC_PATH={ada2_ui_public_path}: {e}")

        @app.get("/ada2-injected/lipsync-en.mjs", include_in_schema=False)
        async def lipsync_en_mjs():
            # Serve the module from the project tree by default; allow env override
            default_path = os.path.join(os.path.dirname(__file__), "assets", "web", "lipsync-en.mjs")
            path = os.getenv("LIPSYNC_EN_PATH", default_path)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    src = f.read()
                return Response(content=src, media_type="application/javascript")
            except Exception as e:
                logger.warning(f"Could not read lipsync-en module from {path}: {e}")
                # Minimal fallback class to keep page working
                src = (
                    "export class LipsyncEn {\n"
                    "  preProcessText(s){ return (s||'').toString(); }\n"
                    "  wordsToVisemes(w){ const v=[]; const t=[]; const d=[]; let T=0; const s=(w||'').toLowerCase(); for(const ch of s){ let viseme=null; if('pbm'.includes(ch)) viseme='PP'; else if('fv'.includes(ch)) viseme='FF'; else if('szx'.includes(ch)) viseme='SS'; else if('td'.includes(ch)) viseme='DD'; else if('kgq'.includes(ch)) viseme='kk'; else if('n'.includes(ch)) viseme='nn'; else if('r'.includes(ch)) viseme='RR'; else if(ch==='a') viseme='aa'; else if(ch==='e') viseme='E'; else if('iy'.includes(ch)) viseme='I'; else if(ch==='o') viseme='O'; else if('uw'.includes(ch)) viseme='U'; if(viseme){ v.push(viseme); t.push(T); d.push(1); T+=1; } } if(!v.length){ v.push('sil'); t.push(0); d.push(1);} return { visemes:v, times:t, durations:d }; }\n"
                    "}\n"
                )
                return Response(content=src, media_type="application/javascript")

        def _inject_subtitle_script(html: str) -> str:
            # Ensure relative paths resolve against /ada2-static/
            if "<base" not in html:
                html = html.replace("<head>", "<head>\n<base href=\"/ada2-static/\">\n")

            # Inject import map for Kokoro dependencies and ADA2 module path if not present
            if "@huggingface/transformers" not in html:
                import_map = (
                    "<script type=\"importmap\">\n"
                    "{\n"
                    "  \"imports\": {\n"
                    "    \"@huggingface/transformers\": \"https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.4.2/dist/transformers.min.js\",\n"
                    "    \"phonemizer\": \"https://cdn.jsdelivr.net/npm/phonemizer@1.2.1/dist/phonemizer.min.js\",\n"
                    "    \"/public/js/ui-utils.js\": \"/ada2-static/js/ui-utils.js\"\n"
                    "  }\n"
                    "}\n"
                    "</script>\n"
                )
                html = html.replace("<head>", f"<head>\n{import_map}")

            # Inject ADA2 UI assets (prefer external mount if available)
            head_includes = (
                f'<link rel="stylesheet" href="{js_base}/css/text-highlighting.css">\n'
                f'<script src="{js_base}/js/widget-styles.js"></script>\n'
                f'<script type="module" src="{js_base}/js/ui-utils.js"></script>\n'
                f'<script src="{js_base}/js/text-highlighter.js"></script>\n'
                f'<script type="module" src="{js_base}/js/document-utils.js"></script>\n'
                f'<script src="{js_base}/js/document-widget.js"></script>\n'
                f'<script src="{js_base}/js/widget-manager.js"></script>\n'
                f'<script src="/ada2-static/js/reader-webrtc.js"></script>\n'
                '<script type="module" src="/ada2-static/js/kokoro-bootstrap.mjs"></script>\n'
            )
            if "/ada2-static/js/document-widget.js" not in html:
                html = html.replace("</head>", head_includes + "</head>")

            # Try to expose the TalkingHead instance on the ADA2 client
            if "await this.avatar.showAvatar(" in html and "window.__TH_AVATAR__" not in html:
                html = html.replace(
                    "await this.avatar.showAvatar(",
                    "window.__TH_AVATAR__ = this.avatar; await this.avatar.showAvatar(",
                )

            injection = (
                "<script>\n"
                "(function(){\n"
                "  // Reduce browser console noise: keep only errors\n"
                "  try{ const __noop__=()=>{}; console.log=__noop__; console.info=__noop__; console.debug=__noop__; console.warn=__noop__; }catch(e){}\n"
                "  const OrigPC = window.RTCPeerConnection;\n"
                "  if(!OrigPC) return;\n"
                "  // Ensure lipsync processor is loaded when avatar is ready. Fallback to shim if module shape differs.\n"
                "  async function ensureLipsync(){\n"
                "    try{\n"
                "      const head = window.__TH_AVATAR__; if(!head) return; const lang = ((head.avatar && head.avatar.lipsyncLang) || 'en').toLowerCase(); head.lipsync = head.lipsync || {}; if(head.lipsync[lang]) return;\n"
                "      let mod = null; try{ mod = await import('/ada2-injected/lipsync-' + lang + '.mjs'); }catch(e){ console.warn('[Ada2DC] lipsync import failed', e); }\n"
                "      let obj = null;\n"
                "      if(mod){ const cls = mod['Lipsync' + lang.charAt(0).toUpperCase() + lang.slice(1)]; if(typeof cls === 'function'){ try{ obj = new cls(); }catch(e){ obj = null; } } if(!obj && (mod.default || mod['lipsync' + lang.charAt(0).toUpperCase() + lang.slice(1)])){ const base = mod.default || mod['lipsync' + lang.charAt(0).toUpperCase() + lang.slice(1)]; obj = { preProcessText: (s)=> (s||'').toString(), wordsToVisemes: (word)=>{ const w=(word||'').toLowerCase(); const seq=[]; const push=(v)=>{ if(!v) return; seq.push(v); }; for(let i=0;i<w.length;i++){ const ch=w[i]; const pair=w.slice(i,i+2); if(pair==='th'){ push('TH'); i++; continue;} if(pair==='ch'||pair==='sh'||pair==='jh'){ push('CH'); i++; continue;} if('pbm'.includes(ch)){ push('PP'); continue;} if('fv'.includes(ch)){ push('FF'); continue;} if('szx'.includes(ch)){ push('SS'); continue;} if('dt'.includes(ch)){ push('DD'); continue;} if('kgq'.includes(ch)){ push('kk'); continue;} if('n'.includes(ch)){ push('nn'); continue;} if('r'.includes(ch)){ push('RR'); continue;} if(ch==='a'){ push('aa'); continue;} if(ch==='e'){ push('E'); continue;} if(ch==='i'||ch==='y'){ push('I'); continue;} if(ch==='o'){ push('O'); continue;} if(ch==='u'||ch==='w'){ push('U'); continue;} } if(seq.length===0) seq.push('sil'); const times=[]; const durations=[]; for(let i=0;i<seq.length;i++){ times.push(i); durations.push(1); } return { visemes: seq, times: times, durations: durations }; } }; } }\n"
                "      if(!obj){ // final minimal shim\n"
                "        obj = { preProcessText: (s)=> (s||'').toString(), wordsToVisemes: (word)=>{ const w=(word||'').toLowerCase(); const v = /[aeiou]/.test(w) ? 'aa' : 'PP'; return { visemes:[v], times:[0], durations:[1] }; } };\n"
                "      }\n"
                "      head.lipsync[lang] = obj; console.log('[Ada2DC] lipsync ready for', lang);\n"
                "    }catch(e){ /*ignore*/ }\n"
                "  }\n"
                "  setInterval(ensureLipsync, 1000);\n"
                "  // Base64 -> ArrayBuffer\n"
                "  function b64ToBuf(b64){ try{ const bin=atob(b64); const len=bin.length; const buf=new ArrayBuffer(len); const arr=new Uint8Array(buf); for(let i=0;i<len;i++){arr[i]=bin.charCodeAt(i);} return buf; }catch(e){ return null; } }\n"
                "  // State for lipsync assembly\n"
                "  window.__ttsBuf = window.__ttsBuf || {};\n"
                "  window.__ttsMeta = window.__ttsMeta || {};\n"
                "  function __centerOverAvatar(el){\n"
                "    try{\n"
                "      const ac = document.getElementById('avatar-container');\n"
                "      const r = ac ? ac.getBoundingClientRect() : { left: (window.innerWidth/2-1), width: 2 };\n"
                "      const cx = r.left + (r.width/2);\n"
                "      el.style.position = 'fixed';\n"
                "      el.style.left = (cx)+'px';\n"
                "      el.style.transform = 'translateX(-50%)';\n"
                "      el.style.maxWidth = Math.max(200, Math.round(r.width - 80)) + 'px';\n"
                "      el.style.bottom = '80px';\n"
                "      el.style.zIndex = 1100;\n"
                "    }catch(e){}\n"
                "  }\n"
                "  function getBox(){\n"
                "    let el = document.getElementById('subtitles');\n"
                "    if(!el){ el = document.createElement('div'); el.id='subtitles'; el.style.padding='8px 12px'; el.style.background='rgba(0,0,0,0.6)'; el.style.borderRadius='10px'; el.style.fontSize='18px'; el.style.lineHeight='1.25'; el.style.maxHeight='3.75em'; el.style.textAlign='center'; el.style.color='#fff'; el.style.pointerEvents='none'; el.style.overflow='hidden'; el.style.display='none'; el.style.webkitLineClamp=3; el.style.webkitBoxOrient='vertical'; document.body.appendChild(el);}\n"
                "    __centerOverAvatar(el);\n"
                "    return el;\n"
                "  }\n"
                "  // Try to reuse the existing status label in the ADA2 UI, e.g., 'Avatar Ready' or 'Voice chat connected'.\n"
                "  function findStatusLabel(){\n"
                "    const texts = ['avatar ready','voice chat connected','speak now'];\n"
                "    const nodes = document.querySelectorAll('div,span,p');\n"
                "    for(const n of nodes){ const t=(n.textContent||'').toLowerCase(); for(const key of texts){ if(t.includes(key)){ return n; } } }\n"
                "    return null;\n"
                "  }\n"
                "  let __statusEl=null; let __statusOrig=''; let __toolActive=false; let __speakingActive=false; let __overlayEl=null;\n"
                "  function ensureStatusEl(){ try{ if(!__statusEl){ __statusEl = findStatusLabel(); if(__statusEl){ __statusOrig = __statusEl.textContent||''; } } }catch(e){} }\n"
                "  function setStatusText(text){ ensureStatusEl(); if(!__statusEl) return; __statusEl.textContent = text; }\n"
                "  function setStatusHidden(h){ ensureStatusEl(); if(!__statusEl) return; __statusEl.style.visibility = h ? 'hidden' : 'visible'; }\n"
                "  function ensureOverlay(){ if(__overlayEl) return __overlayEl; ensureStatusEl(); if(!__statusEl) return null; const r = __statusEl.getBoundingClientRect(); const d=document.createElement('div'); d.id='tool-overlay'; d.style.position='fixed'; d.style.left=(r.left)+'px'; d.style.top=(r.top)+'px'; d.style.display='none'; d.style.zIndex=9999; d.style.pointerEvents='none'; d.style.background='rgba(0,0,0,0.55)'; d.style.borderRadius='8px'; d.style.fontSize='13px'; d.style.letterSpacing='0.2px'; d.style.color='#fff'; d.style.alignItems='center'; d.style.justifyContent='center'; d.style.textAlign='center'; d.style.padding='6px 10px'; d.style.boxSizing='border-box'; d.style.whiteSpace='nowrap'; document.body.appendChild(d); __overlayEl=d; return d; }\n"
                "  function positionOverlay(){ try{ const r=(__statusEl||document.body).getBoundingClientRect(); if(__overlayEl){ __overlayEl.style.left=(r.left||18)+'px'; __overlayEl.style.top=(r.top||18)+'px'; } }catch(e){} }\n"
                "  function showOverlay(text){ const d=ensureOverlay(); if(!d) return; positionOverlay(); d.textContent = text||''; d.style.display='inline-flex'; setStatusHidden(true); }\n"
                "  function hideOverlay(){ if(__overlayEl){ __overlayEl.style.display='none'; } setStatusHidden(false); }\n"
                "  /* removed hide/show of underlying label to avoid blank screen */\n"
                "  function holdLabel(label){ showOverlay(label); }\n"
                "  function quietLabel(){ showOverlay(''); }\n"
                "  function releaseLabel(){ hideOverlay(); }\n"
                "  function attachChannel(ch){\n"
                "    if(!ch) return;\n"
                "    ch.onopen = () => { console.log('[Ada2DC] open'); try { ch.send('ping-' + Date.now()); } catch(e){};\n"
                "      if(!window.__pcPing){ window.__pcPing = setInterval(()=>{ try{ ch.send('ping-' + Date.now()) }catch(e){} }, 1000);}\n"
                "    };\n"
                "    ch.onclose = () => { console.log('[Ada2DC] close'); if(window.__pcPing){ clearInterval(window.__pcPing); window.__pcPing=null; } };\n"
                "    ch.onmessage = (ev) => {\n"
                "      let msg = null; try{ msg = JSON.parse(ev.data); }catch(e){ return; }\n"
                "      const box = getBox();\n"
                "      switch(msg && msg.type){\n"
                "        case 'subtitle_start': /*console.log('[Ada2DC] subtitle_start');*/ __centerOverAvatar(box); box.textContent=''; box.style.display='-webkit-box'; __speakingActive=true; /* no overlay change here to avoid flicker */ break;\n"
                "        case 'subtitle_delta': /*console.log('[Ada2DC] subtitle_delta', msg.text);*/ __centerOverAvatar(box); box.textContent = (msg.text||''); box.style.display='-webkit-box'; try{ if(window.documentWidget && window.documentWidget.textHighlighter && window.documentWidget.textHighlighter.isInitialized){ setTimeout(()=>{ try{ window.documentWidget.textHighlighter.highlightText(String(msg.text||'')); }catch(e){} }, 50);} }catch(e){} break;\n"
                "        case 'subtitle_end': /*console.log('[Ada2DC] subtitle_end');*/ __centerOverAvatar(box); box.textContent = (msg.text||''); box.style.display = (box.textContent?'-webkit-box':'none'); __speakingActive=false; releaseLabel(); __toolActive=false; break;\n"
                "        case 'assistant_full_text': try{ if(window.chatWidget && window.chatWidget.addToConversation){ window.chatWidget.addToConversation('assistant', String(msg.text||'')); } }catch(e){} break;\n"
                "        case 'user_text': try{ if(window.chatWidget && window.chatWidget.addToConversation){ window.chatWidget.addToConversation('user', String(msg.text||'')); } }catch(e){} break;\n"
                "        case 'tts_interrupt':\n"
                "          console.log('[Ada2DC] tts_interrupt'); try{ window.__ttsBuf = {}; window.__ttsMeta = {}; if(window.__TH_AVATAR__ && window.__TH_AVATAR__.stopSpeaking){ window.__TH_AVATAR__.stopSpeaking(); } }catch(e){} holdLabel('User'); break;\n"
                "        case 'log_tool':\n"
                "          try{ const phase = (msg.phase||''); if(phase==='llm_only'){ /* ignore: no Local LLM display */ break; } const name = (msg.name||''); let label='Tool'; if(name==='google_search'){ label='Google Search'; } else if(name==='get_current_weather'){ label='Weather Search'; } if (phase === 'start') {__toolActive=true; holdLabel(label); } else if (phase === 'end') {__toolActive = false; releaseLabel(); }}catch(e){}\n"
                "          break;\n"
                "        case 'tts_sentence_start':\n"
                "          console.log('[Ada2DC] sentence_start', msg.id); window.__ttsBuf[msg.id] = []; window.__ttsMeta[msg.id] = { text: msg.text||'', sample_rate: msg.sample_rate||24000 };\n"
                "          break;\n"
                "        case 'tts_sentence_chunk':\n"
                "          if(window.__ttsBuf[msg.id]){ const buf = b64ToBuf(msg.chunk); if(buf){ window.__ttsBuf[msg.id].push(buf); } }\n"
                "          break;\n"
                "        case 'tts_sentence_end':\n"
                "          console.log('[Ada2DC] sentence_end', msg.id); (async function(){\n"
                "            const bufs = window.__ttsBuf[msg.id]||[]; const meta = window.__ttsMeta[msg.id]||{}; delete window.__ttsBuf[msg.id]; delete window.__ttsMeta[msg.id];\n"
                "            if(!bufs.length) return;\n"
                "            const head = window.__TH_AVATAR__ || null;\n"
                "            if(!head || !head.speakAudio){ return; }\n"
                "            try{ head.opt = head.opt || {}; head.opt.pcmSampleRate = meta.sample_rate||24000; }catch(e){}\n"
                "            // Build word timings from audio length with phoneme-aware weighting\n"
                "            const text = (meta.text||'').trim(); const words = text ? text.split(' ').filter(Boolean) : [];\n"
                "            let totalBytes = 0; for(let i=0;i<bufs.length;i++){ totalBytes += bufs[i].byteLength; }\n"
                "            const sr = meta.sample_rate||24000; const totalMs = Math.max(200, Math.round((totalBytes/2)/sr*1000));\n"
                "            const trimStartMs = 50, trimEndMs = 200; const usableMs = Math.max(120, totalMs - trimStartMs - trimEndMs);\n"
                "            const n = Math.max(1, words.length); const wtimes = []; const wdurations = [];\n"
                "            const lang = (head.avatar && head.avatar.lipsyncLang) || 'en'; const lproc = (head.lipsync && head.lipsync[lang]) || null;\n"
                "            const punctMap = { ',':1.1, ';':1.2, ':':1.2, '.':1.6, '!':1.6, '?':1.6, '…':1.8 };\n"
                "            const baseMin = 1.0, charFactor = 0.15; const weights = [];\n"
                "            for(let i=0;i<n;i++){ const raw = words[i]; let w=baseMin; let core=raw; const m = raw.match(/^(.*?)([.,!?;:…]+)$/); if(m){ core = m[1]||raw; const tail = m[2]; for(const ch of tail){ w += (punctMap[ch]||0); } }\n"
                "              if(lproc){ try{ const prep = lproc.preProcessText(core||''); const val = lproc.wordsToVisemes(prep); if(val && Array.isArray(val.durations) && val.durations.length){ w += val.durations.reduce((a,b)=>a+(isFinite(b)?b:0),0); } }catch(e){} }\n"
                "              w += charFactor * Math.max(0, (core||'').length - 1); weights.push(Math.max(0.5, w)); }\n"
                "            const sumW = weights.reduce((a,b)=>a+b,0) || 1; let acc=0;\n"
                "            for(let i=0;i<n;i++){ let dur = Math.max(70, Math.round(usableMs * (weights[i]/sumW))); if(i===n-1){ dur = Math.max(140, usableMs - acc); } wtimes.push(acc); wdurations.push(dur); acc += dur; }\n"
                "            try{ head.setMixerGain(0, null); }catch(e){}\n"
                "            try{ console.log('[Ada2DC] speakAudio', {wordsCount:words.length, totalMs}); head.speakAudio({ audio: bufs, words: words, wtimes: wtimes, wdurations: wdurations }, { lipsyncLang: (head.avatar && head.avatar.lipsyncLang) || 'en' }); }catch(e){ console.warn('[Ada2DC] speakAudio error', e); }\n"
                "          })();\n"
                "          break;\n"
                "      }\n"
                "    };\n"
                "  }\n"
                "  window.RTCPeerConnection = function(cfg){ const pc = new OrigPC(cfg); try{ const dc = pc.createDataChannel('app', {ordered:true}); console.log('[Ada2DC] created'); attachChannel(dc); }catch(e){ console.warn('[Ada2DC] create error', e);} pc.addEventListener('datachannel', (ev)=> attachChannel(ev.channel)); return pc; };\n"
                "  window.RTCPeerConnection.prototype = OrigPC.prototype;\n"
                "  // Nudge AudioContext on user gesture (connect button)\n"
                "  document.addEventListener('click', (ev)=>{ const t = ev.target; if(t && t.id==='connect-btn'){ setTimeout(()=>{ try{ const head = window.__TH_AVATAR__; if(head && head.audioCtx && head.audioCtx.state!=='running'){ head.audioCtx.resume(); } }catch(e){} ensureLipsync(); }, 50); } });\n"
                "  // Upload button removed; widget provides its own upload UI.\n"
                "  function addLibraryBtn(){ try{ if(document.getElementById('document-widget-btn')) return; var b=document.createElement('button'); b.id='document-widget-btn'; b.textContent='📖 Library'; b.style.cssText='position:fixed;left:20px;bottom:72px;z-index:1000;background:linear-gradient(45deg, #667eea, #764ba2);color:#fff;border:none;padding:10px 14px;border-radius:8px;cursor:pointer;font-size:14px;box-shadow:0 4px 12px rgba(102,126,234,.30)'; b.onclick=async function(){ try{ if(window.readerRTC && window.readerRTC.connect){ await window.readerRTC.connect(); } if(window.chatWidget && typeof window.chatWidget.hide==='function'){ window.chatWidget.hide(); } if(window.documentWidget){ if(typeof window.documentWidget.returnToLibrary==='function'){ await window.documentWidget.returnToLibrary(); } if(window.widgetManager && window.widgetManager.showWidget){ window.widgetManager.showWidget('document', ()=> window.documentWidget.show()); } else { window.documentWidget.show(); } } }catch(e){} }; document.body.appendChild(b);}catch(e){} }\n"
                "  function init(){ setTimeout(addLibraryBtn, 300); }\n"
                "  if(document.readyState==='complete' || document.readyState==='interactive'){ init(); } else { document.addEventListener('DOMContentLoaded', init); }\n"
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

    # Redirect legacy /ada2 path to /ada2-ui
    @app.get("/ada2", include_in_schema=False)
    async def legacy_redirect():
        return RedirectResponse(url="/ada2-ui/")

    # ---------------------------
    # Document/book API endpoints (ADA2-compatible) — lazy imports
    # ---------------------------
    @app.post("/api/documents/upload")
    async def api_upload_document_file(file: UploadFile = File(...)):
        try:
            from modules.books.handlers import upload_document_file as _upload_document_file

            logger.info("/api/documents/upload: received file name=%r content_type=%r", file.filename, file.content_type)
            content = await file.read()
            filename = file.filename or "uploaded.epub"
            success, message, doc_info = await _upload_document_file(content, filename)
            logger.info("/api/documents/upload: success=%s title=%r", bool(success), (doc_info or {}).get("title") if doc_info else None)
            return {"success": bool(success), "message": message, "document": doc_info}
        except Exception as e:
            # Return JSON error for frontend compatibility instead of HTTP 500
            logger.error("/api/documents/upload: error=%s", e)
            return {"success": False, "message": str(e)}

    @app.post("/api/documents/upload-path")
    async def api_upload_document_path(request: dict):
        try:
            from modules.books.handlers import upload_document as _upload_document_path

            file_path = str(request.get("file_path", ""))
            logger.info("/api/documents/upload-path: file_path=%r", file_path)
            success, message, doc_info = await _upload_document_path(file_path)
            logger.info("/api/documents/upload-path: success=%s title=%r", bool(success), (doc_info or {}).get("title") if doc_info else None)
            return {"success": bool(success), "message": message, "document": doc_info}
        except Exception as e:
            logger.error("/api/documents/upload-path: error=%s", e)
            return {"success": False, "message": str(e)}

    @app.get("/api/documents/list")
    async def api_list_documents():
        try:
            from modules.books.handlers import get_document_list as _get_document_list

            success, message, documents = await _get_document_list()
            logger.info("/api/documents/list: count=%d", len(documents or {}))
            return {
                "success": bool(success),
                "message": message,
                "documents": documents or {},
            }
        except Exception as e:
            logger.error("/api/documents/list: error=%s", e)
            return {"success": False, "message": str(e), "documents": {}}

    @app.post("/api/documents/delete")
    async def api_delete_document(request: dict):
        try:
            from modules.books.chroma_store import get_store as _get_store

            document_id = str(request.get("document_id", ""))
            store = _get_store()
            ok = await store.delete_document(document_id)
            logger.info("/api/documents/delete: id=%r success=%s", document_id, bool(ok))
            return {
                "success": bool(ok),
                "message": f"Document {document_id} deleted" if ok else "Delete failed",
            }
        except Exception as e:
            logger.error("/api/documents/delete: error=%s", e)
            return {"success": False, "message": str(e)}

    @app.post("/api/documents/query")
    async def api_document_query(request: dict):
        try:
            from modules.books.query_parser import parse_document_query as _parse_doc_query

            q = str(request.get("query", ""))
            logger.info("/api/documents/query: q=%r", q)
            res = await _parse_doc_query(q)
            logger.info("/api/documents/query: ok=%s type=%r", bool(res.get("success")), res.get("type"))
            return res
        except Exception as e:
            logger.error("/api/documents/query: error=%s", e)
            return {"success": False, "message": str(e)}

    @app.post("/api/tts/read")
    async def api_tts_read(request: dict):
        """Speak arbitrary text using the active pipeline's TTS, with avatar lipsync.

        Body: { "text": "...", "pc_id": "optional" }
        """
        try:
            from modules.tts_bridge import get_speaker

            text = str(request.get("text", "")).strip()
            pc_id = request.get("pc_id")
            if not text:
                return {"success": False, "message": "Missing text"}
            speak = get_speaker(pc_id)
            if not speak:
                return {"success": False, "message": "No active voice session"}
            await speak(text)
            return {"success": True}
        except Exception as e:
            logger.error("/api/tts/read: error=%s", e)
            return {"success": False, "message": str(e)}

    @app.post("/api/chat/send")
    async def api_chat_send(request: dict):
        """Send a user message to the existing LLM path for this session.

        Body: { "text": "...", "pc_id": "optional" }
        """
        try:
            from modules.chat_bridge import get_sender

            text = str(request.get("text", "")).strip()
            pc_id = request.get("pc_id")
            if not text:
                return {"success": False, "message": "Missing text"}
            sender = get_sender(pc_id)
            if not sender:
                return {"success": False, "message": "No active chat session"}
            await sender(text)
            return {"success": True}
        except Exception as e:
            logger.error("/api/chat/send: error=%s", e)
            return {"success": False, "message": str(e)}

    # Manage active peer connections by pc_id
    pcs_map: Dict[str, SmallWebRTCConnection] = {}

    @app.post("/api/offer")
    async def offer(request: dict, background_tasks: BackgroundTasks):
        pc_id = request.get("pc_id")
        mode = str(request.get("mode") or "chat").lower().strip()

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
            # Set mode for bot (chat/reader)
            try:
                setattr(bot_module, "BOT_MODE", mode)
            except Exception:
                pass
            background_tasks.add_task(bot_module.bot, runner_args)

        answer = connection.get_answer()
        if answer is None:
            # If negotiation hasn't produced an answer, signal a server error.
            # This also narrows the type for static checkers.
            raise HTTPException(status_code=503, detail="SDP answer not available")
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
        default=os.getenv(
            "ADA2_CLIENT_PATH",
            os.path.join(os.path.dirname(__file__), "assets", "ada2-client"),
        ),
        help=(
            "Path to ADA2/pipecat-client build directory. "
            "Defaults to assets/ada2-client inside this project."
        ),
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
