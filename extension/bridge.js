/* LocalAI Feed — bridge (content script on the chat.html page)
   เชื่อมระหว่างหน้า chat.html (file://) กับ extension:
   - รับคำขอ LOCALAI_FEED_REQUEST จากหน้า -> ดึงฟีดจาก background -> ส่งกลับ
   - เฝ้าดู chrome.storage 'feed' -> push เข้าไปหน้าเมื่อมีอัปเดต
*/
(function(){
  // ทำงานเฉพาะหน้า LocalAI Chat เท่านั้น
  if(!document.getElementById('feedDrawer') && document.title !== 'Local AI Chat') return;

  function pushToPage(items){
    window.postMessage({ type:'LOCALAI_FEED', items: items || [] }, '*');
  }

  // หน้าเว็บขอฟีด
  window.addEventListener('message', (e) => {
    if(e.source !== window) return;
    const d = e.data;
    if(d && d.type === 'LOCALAI_FEED_REQUEST'){
      try{
        chrome.runtime.sendMessage({ cmd:'getFeed', keywords: d.keywords }, (resp) => {
          if(chrome.runtime.lastError) return;
          if(resp && resp.items) pushToPage(resp.items);
        });
      }catch(err){}
    }
  });

  // push อัตโนมัติเมื่อ storage เปลี่ยน (ได้ข่าว/mention ใหม่)
  try{
    chrome.storage.onChanged.addListener((changes, area) => {
      if(area === 'local' && changes.feed) pushToPage(changes.feed.newValue || []);
    });
    // ส่งข้อมูลที่มีอยู่ตอนโหลดหน้า
    chrome.storage.local.get('feed', (data) => { if(data && data.feed) pushToPage(data.feed); });
  }catch(err){}

  console.log('[LocalAI Feed] bridge active');
})();
