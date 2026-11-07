/**
 * build-prompts.mjs — สร้าง prompt datasheet 3.4 จากส่วนประกอบในโฟลเดอร์นี้
 *   common.txt = กติกาที่ใช้ทุกชนิด (มีช่อง {{1}} {{5}} {{6}} {{7}} {{10}} {{11}} {{12}} {{FORMULAS}})
 *   kind_*.txt = ส่วนเฉพาะชนิด แบ่งด้วยบรรทัด @@<ชื่อส่วน>
 *   ผลลัพธ์ (โฟลเดอร์แม่): PROMPT_PV/INV/BAT/OPT/EV.txt + createdtatsheet.txt (ฉบับรวมทุกชนิด)
 *   แก้เนื้อหาที่ไฟล์ในโฟลเดอร์นี้ แล้วรัน:  node _src/build-prompts.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url)), OUT = path.join(HERE, '..');
const VER = '3.4';
const common = fs.readFileSync(path.join(HERE, 'common.txt'), 'utf8');
const KINDS = ['pv', 'inv', 'bat', 'opt', 'ev'].map((k) => {
  const parts = {};
  let cur = null;
  for (const line of fs.readFileSync(path.join(HERE, `kind_${k}.txt`), 'utf8').split(/\r?\n/)) {
    const m = /^@@([A-Z0-9]+)\s*$/.exec(line);
    if (m) { cur = m[1]; parts[cur] = []; continue; }
    if (cur) parts[cur].push(line);
  }
  for (const p of Object.keys(parts)) parts[p] = parts[p].join('\n').replace(/\s+$/, '');
  return parts;
});

function render(kinds, title, templates, oneKind) {
  const join = (key, sep = '\n\n') => kinds.map((k) => k[key]).filter(Boolean).join(sep);
  const sel = oneKind
    ? `${kinds[0]['1']}\n   ไฟล์ที่แนบมาไม่ใช่${kinds[0].TITLE} ให้หยุดแล้วบอกผู้ใช้ให้ใช้ PROMPT ของชนิดนั้นแทน`
    : `${join('1', '\n')}\n   เอกสารเดียวมีหลายชนิด (เช่น All-in-one ESS ที่มีทั้งอินเวอร์เตอร์และแบต)\n   ให้สร้าง 1 ไฟล์ต่อ 1 ชนิด และระบุใน Notes ว่ามาจากเอกสารเดียวกัน`;
  const s = common
    .replace(/\{\{TITLE\}\}/g, title).replace('{{TEMPLATES}}', templates)
    .replace('{{1}}', sel).replace('{{FORMULAS}}', join('FORMULAS', '\n'))
    .replace('{{5}}', join('5')).replace('{{6}}', join('6')).replace('{{7}}', join('7', '\n'))
    .replace('{{10}}', join('10')).replace('{{11}}', join('11')).replace('{{12}}', join('12'));
  if (/\{\{[A-Z0-9]+\}\}/.test(s)) throw new Error(`ช่องว่างค้าง: ${s.match(/\{\{[A-Z0-9]+\}\}/)[0]}`);
  return s.replace(/\r?\n/g, '\n');
}

for (const k of KINDS) {
  const f = `PROMPT_${k.NAME}.txt`;
  fs.writeFileSync(path.join(OUT, f), render([k], `PROMPT กวาดข้อมูล Datasheet ${k.TITLE} → ASC Studio (เวอร์ชัน ${VER})`, `${k.TEMPLATE} (ไฟล์เดียว)`, true), 'utf8');
  console.log('เขียน', f);
}
fs.writeFileSync(path.join(OUT, 'createdtatsheet.txt'), render(KINDS, `PROMPT สำหรับกวาดข้อมูล Datasheet ลงพารามิเตอร์อุปกรณ์ ทุกชนิด (เวอร์ชัน ${VER})`, `ทั้ง 5 ไฟล์ (${KINDS.map((k) => k.TEMPLATE).join(' · ')})`, false), 'utf8');
console.log('เขียน createdtatsheet.txt (ฉบับรวม)');
