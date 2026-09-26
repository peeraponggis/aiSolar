/* ปลั๊กอินตัวอย่าง: แทรกวันเวลาปัจจุบัน
   - เพิ่มปุ่มบนแถบบน + คำสั่ง /เวลา
   API ที่ใช้: LocalAI.addButton, LocalAI.addCommand, LocalAI.insertInput, LocalAI.log
*/
LocalAI.register({
  name: "วันเวลา",
  version: "1.0",
  init() {
    const now = () => new Date().toLocaleString('th-TH', { dateStyle: 'full', timeStyle: 'short' });

    // ปุ่มบนแถบบน -> แทรกวันเวลาในกล่องพิมพ์
    LocalAI.addButton('📅', () => LocalAI.insertInput(now()), 'แทรกวันเวลาปัจจุบัน');

    // คำสั่ง /เวลา -> ตอบวันเวลาโดยไม่ต้องเรียกโมเดล
    LocalAI.addCommand('/เวลา', () => {
      LocalAI.addAssistantMessage('ตอนนี้: ' + now());
      return true; // handled
    });

    LocalAI.log('ปลั๊กอิน "วันเวลา" พร้อมใช้งาน', 'ok');
  }
});
