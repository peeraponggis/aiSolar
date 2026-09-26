/* LocalAI Feed — background service worker
   - ดึงข่าว AI/เทคโนโลยีจาก RSS (ฟรี ไม่ต้องใช้ key)
   - รับ social mentions จาก content script (social.js)
   - เก็บรวมใน chrome.storage.local 'feed' ให้ bridge.js ส่งเข้า chat.html
*/
const NEWS_FEEDS = [
  { url: 'https://news.google.com/rss/search?q=(AI%20OR%20%22language%20model%22%20OR%20LLM%20OR%20ปัญญาประดิษฐ์)%20when:3d&hl=th&gl=TH&ceid=TH:th', source: 'Google News (ไทย)' },
  { url: 'https://news.google.com/rss/search?q=(AI%20OR%20LLM%20OR%20%22open%20model%22%20OR%20Ollama)%20when:2d&hl=en-US&gl=US&ceid=US:en', source: 'Google News' },
  { url: 'https://hnrss.org/newest?q=AI+OR+LLM+OR+model+OR+GPU&count=20', source: 'Hacker News' }
];
const DEFAULT_KEYWORDS = ['peerapong','aisolar','ai','พีระพงษ์','อ.พี'];

function stripTags(s){ return (s||'').replace(/<[^>]+>/g,' ').replace(/&[a-z]+;/gi,' ').replace(/\s+/g,' ').trim(); }
function pick(block, tag){
  const m = block.match(new RegExp('<'+tag+'[^>]*>([\\s\\S]*?)<\\/'+tag+'>','i'));
  if(!m) return '';
  let v = m[1].trim();
  const cd = v.match(/<!\[CDATA\[([\s\S]*?)\]\]>/); if(cd) v = cd[1];
  return v.trim();
}
function parseRSS(xml, source){
  const items = [];
  const blocks = xml.split(/<item[\s>]/i).slice(1);
  for(const raw of blocks){
    const b = '<item '+raw;
    const title = stripTags(pick(b,'title'));
    let link = pick(b,'link');
    if(!link){ const lm = b.match(/<link[^>]*href="([^"]+)"/i); if(lm) link = lm[1]; }
    link = stripTags(link);
    const date = pick(b,'pubDate') || pick(b,'dc:date') || pick(b,'published');
    const desc = stripTags(pick(b,'description')).slice(0,200);
    if(title){ items.push({ type:'news', source, title, url:link, snippet:desc, time: date? Date.parse(date)||Date.now() : Date.now() }); }
  }
  return items;
}
async function fetchNews(){
  let all = [];
  for(const f of NEWS_FEEDS){
    try{
      const res = await fetch(f.url, { cache:'no-store' });
      if(!res.ok) continue;
      const xml = await res.text();
      all = all.concat(parseRSS(xml, f.source).slice(0, 15));
    }catch(e){ /* ข้าม feed ที่ล้มเหลว */ }
  }
  return all;
}
async function mergeStore(newItems){
  const cur = (await chrome.storage.local.get('feed')).feed || [];
  const seen = new Set(cur.map(x => x.url || x.title));
  let added = 0;
  for(const it of newItems){ const k = it.url || it.title; if(k && !seen.has(k)){ cur.unshift(it); seen.add(k); added++; } }
  const trimmed = cur.slice(0, 300);
  await chrome.storage.local.set({ feed: trimmed, updated: Date.now() });
  return added;
}
async function refreshNews(){ const n = await fetchNews(); await mergeStore(n); }

chrome.runtime.onInstalled.addListener(async () => {
  const kw = (await chrome.storage.local.get('keywords')).keywords;
  if(!kw) await chrome.storage.local.set({ keywords: DEFAULT_KEYWORDS });
  chrome.alarms.create('refresh', { periodInMinutes: 30 });
  refreshNews();
});
chrome.runtime.onStartup.addListener(() => refreshNews());
chrome.alarms.onAlarm.addListener(a => { if(a.name === 'refresh') refreshNews(); });

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    if(msg.cmd === 'getFeed'){
      if(msg.keywords) await chrome.storage.local.set({ keywords: msg.keywords });
      await refreshNews();
      const data = await chrome.storage.local.get('feed');
      sendResponse({ items: data.feed || [] });
    } else if(msg.cmd === 'social'){
      const added = await mergeStore(msg.items || []);
      sendResponse({ added });
    } else if(msg.cmd === 'getKeywords'){
      const data = await chrome.storage.local.get('keywords');
      sendResponse({ keywords: data.keywords || DEFAULT_KEYWORDS });
    }
  })();
  return true; // async response
});
