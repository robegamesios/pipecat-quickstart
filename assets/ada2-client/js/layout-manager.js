(function(){
  const LayoutManager = {
    set(opts){
      const layout = (opts && opts.layout) || 'landscape';
      const avatar = (opts && opts.avatar) || (layout==='landscape'?'left':'top');
      document.body.setAttribute('data-layout', layout);
      document.body.setAttribute('data-avatar', avatar);
      document.body.classList.add('split-layout');
    }
  };
  window.LayoutManager = LayoutManager;
  // Default
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    LayoutManager.set({ layout: 'landscape', avatar: 'left' });
  } else {
    document.addEventListener('DOMContentLoaded', function(){ LayoutManager.set({ layout: 'landscape', avatar: 'left' }); });
  }
  // Inject CSS for split layouts
  if (!document.getElementById('split-layout-css')){
    const s = document.createElement('style');
    s.id='split-layout-css';
    s.textContent = [
      '.split-layout #avatar-container{ position:absolute; top:0; left:0; height:100vh; width:50vw; }',
      // Let widgets manage their own visibility/animation; only constrain size/position here
      '.split-layout .chatgpt-widget{ position:absolute; top:0; right:0; width:50vw; height:100vh; }',
      '[data-layout="portrait"].split-layout #avatar-container{ position:absolute; top:0; left:0; width:100vw; height:50vh; }',
      '[data-layout="portrait"].split-layout .chatgpt-widget{ position:absolute; bottom:0; left:0; width:100vw; height:50vh; }',
      // Subtitles centered under avatar
      '.split-layout #subtitles{ left: 25vw; transform: translateX(-50%); }',
      '[data-layout="portrait"].split-layout #subtitles{ left: 50%; }',
      // Max width constraint
      '.app-root{ max-width: 1728px; margin: 0 auto; position:relative; }'
    ].join('\n');
    document.head.appendChild(s);
  }
})();
