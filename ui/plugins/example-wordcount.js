/* ปลั๊กอินตัวอย่าง: นับคำ/ตัวอักษรของคำตอบ AI อัตโนมัติ
   - ใช้ hook onReply เพื่อ log สถิติหลังโมเดลตอบ
   - เพิ่มคำสั่ง /นับ <ข้อความ>
   API: LocalAI.onReply, LocalAI.addCommand, LocalAI.addAssistantMessage, LocalAI.log
*/
LocalAI.register({
  name: "นับคำ",
  version: "1.0",
  init() {
    // หลังโมเดลตอบทุกครั้ง -> log จำนวนคำ/ตัวอักษร
    LocalAI.onReply((text) => {
      const words = (text.trim().match(/\S+/g) || []).length;
      LocalAI.log(`📊 คำตอบ: ${words} คำ · ${text.length} ตัวอักษร`, 'info');
    });

    // /นับ <ข้อความ> -> นับให้ทันที
    LocalAI.addCommand('/นับ', (arg) => {
      const t = (arg || '').trim();
      if (!t) { LocalAI.addAssistantMessage('พิมพ์: /นับ ตามด้วยข้อความที่ต้องการนับ'); return true; }
      const words = (t.match(/\S+/g) || []).length;
      LocalAI.addAssistantMessage(`ข้อความนี้มี **${words} คำ** และ **${t.length} ตัวอักษร**`);
      return true;
    });

    LocalAI.log('ปลั๊กอิน "นับคำ" พร้อมใช้งาน', 'ok');
  }
});
