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
    async connect(){
      if (this.isConnected() || this.connecting) return true;
      this.connecting = true;
      try{
        const pc = new RTCPeerConnection();
        // Receive-only audio
        try{ pc.addTransceiver('audio', { direction: 'recvonly' }); }catch(_){}
        pc.ontrack = (ev)=>{ if(ev && ev.streams && ev.streams[0]) playRemoteAudio(ev.streams[0]); };
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        const resp = await fetch('/api/offer', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ type:'offer', sdp: offer.sdp, mode: 'reader' })
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
