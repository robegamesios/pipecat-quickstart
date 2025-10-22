(function(){
  function playRemoteAudio(stream){
    try{
      const a = new Audio();
      a.autoplay = true; a.muted = false; a.volume = 1.0; a.srcObject = stream; a.play().catch(()=>{});
    }catch(_){}
  }

  const ReaderRTC = {
    pc: null,
    pc_id: null,
    connecting: false,
    isConnected(){ return !!(this.pc && this.pc.connectionState === 'connected'); },
    disconnect(){
      try { if (this.pc) { this.pc.close(); } } catch(_){}
      this.pc = null;
      this.pc_id = null;
      this.connecting = false;
    },
    async connect(){
      if (this.isConnected() || this.connecting) return true;
      this.connecting = true;
      try{
        const pc = new RTCPeerConnection();
        // Receive-only audio
        try{ pc.addTransceiver('audio', { direction: 'recvonly' }); }catch(_){}
        pc.ontrack = (ev)=>{ if(ev && ev.streams && ev.streams[0]) playRemoteAudio(ev.streams[0]); };
        // Receive app data channel for assistant/user text events
        pc.ondatachannel = (ev) => {
          const ch = ev && ev.channel;
          if (!ch) return;
          ch.onmessage = (e) => {
            let msg=null; try{ msg = JSON.parse(e.data); }catch(_){ return; }
            try{
              if (!window.chatWidget || !window.chatWidget.addToConversation) return;
              if (msg.type === 'assistant_full_text' && typeof msg.text === 'string') {
                window.chatWidget.addToConversation('assistant', String(msg.text||''));
              } else if (msg.type === 'user_text' && typeof msg.text === 'string') {
                window.chatWidget.addToConversation('user', String(msg.text||''));
              }
            }catch(_){ }
          };
        };
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        // Stable client id shared with voice chat
        const clientId = (() => {
          try{
            let id = localStorage.getItem('ada2_client_id');
            if(!id){ id = 'c-' + Math.random().toString(36).slice(2); localStorage.setItem('ada2_client_id', id); }
            return id;
          }catch(_){ return null; }
        })();

        const resp = await fetch('/api/offer', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ type:'offer', sdp: offer.sdp, mode: 'reader', client_id: clientId })
        });
        const answer = await resp.json();
        if (!answer || !answer.sdp) throw new Error('No SDP answer');
        this.pc_id = answer.pc_id || null;
        await pc.setRemoteDescription({ type:'answer', sdp: answer.sdp });
        this.pc = pc;
        this.connecting = false;
        return true;
      }catch(e){
        console.warn('ReaderRTC connect failed', e);
        this.connecting = false;
        try{ if(this.pc){ this.pc.close(); } }catch(_){ }
        this.pc = null; this.pc_id = null;
        return false;
      }
    }
  };
  window.readerRTC = ReaderRTC;
})();
