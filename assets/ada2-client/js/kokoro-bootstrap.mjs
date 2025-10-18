// Module bootstrap: load kokorotts and expose window.kokoroSpeak
import { KokoroTTS } from '/ada2-static/modules/kokorotts.mjs';

async function init() {
  try {
    const tts = new KokoroTTS({ device: 'wasm', voice: 'af_heart', language: 'en-us', speed: 1 });
    await tts.load();
    window.kokoroSpeak = function (text, opt, onword) {
      const head = window.__TH_AVATAR__ || null;
      tts.generate(String(text || ''), function (o) {
        if (onword && Array.isArray(o.words)) {
          const start = performance.now();
          for (let i = 0; i < o.words.length; i++) {
            const w = (o.words[i] || '') + ' ';
            const t = (o.wtimes && o.wtimes[i]) || 0;
            setTimeout(() => { try { onword(String(text || ''), 'kokoro-' + start, w); } catch (_) {} }, Math.max(0, t));
          }
        }
        if (head && head.speakAudio) {
          try {
            head.speakAudio(
              { audio: [o.audio], words: o.words || [], wtimes: o.wtimes || [], wdurations: o.wdurations || [] },
              { lipsyncLang: 'en' }
            );
          } catch (e) { console.warn('speakAudio failed', e); }
        }
      });
    };
    window.__kokoroImpl = 'kokorotts';
  } catch (e) {
    console.warn('Kokoro bootstrap failed', e);
  }
}

init();

