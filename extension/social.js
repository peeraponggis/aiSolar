/* LocalAI Feed — social scraper (content script)
   ทำงานเฉพาะบนแท็บโซเชียลที่คุณ "ล็อกอินและเปิดค้างไว้"
   อ่านโพสต์/คอมเมนต์ที่มีคำที่ติดตาม แล้วส่งเข้า LocalAI Chat
   *ไม่แตะรหัสผ่าน ใช้ session ที่ล็อกอินอยู่แล้ว / ไม่เปิดแท็บ = ไม่มีข้อมูล*
*/
(function(){
  const HOST = location.hostname.replace(/^www\./,'');
  const PLATFORM =
    HOST.includes('facebook') ? 'Facebook' :
    HOST.includes('youtube')  ? 'YouTube'  :
    HOST.includes('tiktok')   ? 'TikTok'   : HOST;

  const DEFAULT_KW = ['peerapong','aisolar','พีระพงษ์','อ.พี'];
  let keywords = [];
  const sent = new Set();

  function loadKeywords(cb){
    try{ chrome.storage.local.get('keywords', d => {
      keywords = (d && d.keywords && d.keywords.length) ? d.keywords : DEFAULT_KW;
      cb && cb();
    }); }
    catch(e){ keywords = DEFAULT_KW; cb && cb(); }
  }

  function matches(text){
    const t = text.toLowerCase();
    return keywords.some(k => k && t.includes(String(k).toLowerCase()));
  }

  function nearestLink(el){
    // หา permalink ใกล้ที่สุด
    let n = el;
    for(let i=0;i<6 && n;i++,n=n.parentElement){
      const a = n.querySelector && n.querySelector('a[href*="/watch"],a[href*="/video/"],a[href*="/posts/"],a[href*="/permalink"],a[href*="/reel"],a[href*="/@"]');
      if(a && a.href) return a.href;
    }
    return location.href;
  }

  function scan(){
    if(!keywords.length) return;
    // เลือก container โพสต์ตามแพลตฟอร์ม (กว้างๆ เพื่อรองรับการเปลี่ยน DOM)
    const sels = PLATFORM==='YouTube'
      ? ['ytd-video-renderer','ytd-rich-item-renderer','ytd-comment-thread-renderer','#content-text']
      : PLATFORM==='TikTok'
      ? ['[data-e2e="search_video-item"]','[data-e2e="video-desc"]','[data-e2e="comment-level-1"]','div[class*="DivItemContainer"]']
      : ['[role="article"]','[data-ad-preview="message"]','div[dir="auto"]'];
    const nodes = document.querySelectorAll(sels.join(','));
    const found = [];
    let count = 0;
    for(const node of nodes){
      if(count >= 20) break;
      const text = (node.innerText || '').trim();
      if(text.length < 8 || text.length > 1200) continue;
      if(!matches(text)) continue;
      const key = PLATFORM + '|' + text.slice(0,120);
      if(sent.has(key)) continue;
      sent.add(key);
      found.push({
        type:'social', platform: PLATFORM, source: PLATFORM + ' · แท็บที่เปิดอยู่',
        title: text.slice(0,140), snippet: text.slice(0,220),
        url: nearestLink(node), time: Date.now()
      });
      count++;
    }
    if(found.length){
      try{ chrome.runtime.sendMessage({ cmd:'social', items: found }); }catch(e){}
    }
  }

  // debounce scan
  let t=null;
  function schedule(){ clearTimeout(t); t=setTimeout(scan, 1500); }

  loadKeywords(() => {
    console.log('[LocalAI Feed] social active on', PLATFORM, '— keywords:', keywords);
    setTimeout(scan, 3000);                 // หลังโหลดหน้า
    window.addEventListener('scroll', schedule, { passive:true });
    setInterval(() => { loadKeywords(scan); }, 60000); // สแกนซ้ำทุก 1 นาที + อัปเดต keyword
  });
})();
