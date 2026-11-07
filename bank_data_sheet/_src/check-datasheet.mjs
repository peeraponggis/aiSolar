// ตรวจไฟล์ datasheet .txt ตามข้อ 7.1 ของ PROMPT 3.4 ก่อนนำเข้า ASC Studio
//   node _src/check-datasheet.mjs <ไฟล์.txt ...>   (เทียบชื่อฟิลด์กับแม่แบบในโฟลเดอร์แม่)
import fs from 'node:fs';
const TPL = { PV_MODULE_STRUCTURE: 'PV_MODULE_STRUCTURE.txt', INVERTER_STRUCTURE: 'INVERTER_STRUCTURE.txt', BATTERY_ESS_STRUCTURE: 'BATTERY_ESS_STRUCTURE.txt', OPTIMIZER_STRUCTURE: 'OPTIMIZER_STRUCTURE.txt', EV_CHARGE_STRUCTURE: 'EV_CHARGE_STRUCTURE.txt' };
const ENUM = { Inverter_Type: /^(String|Hybrid|Off-grid|Micro|Central)$/, Phase_Type: /^[13]-Phase$/, Battery_Coupling_Class: /^(HV|LV|None)$/, Battery_Voltage_Class: /^(HV|LV)$/, Off_Grid_Mode: /^(Both|Grid-assist|Stand-alone|None)$/, AC_Coupling_Port: /^(Grid-side|Backup-side|Both|None)$/, Charger_Type: /^(AC|DC)$/, Builtin_RCD_Class: /^(None|Type [AFB])$/, IP_Rating: /^IP\d\d$/, Connector_Form: /^(Socket|Tethered)$/, Charging_Mode: /^Mode [234]$/ };
const keysOf = (t) => t.split('\n').map((l) => /^([A-Za-z][A-Za-z0-9_]*)\s*=/.exec(l)?.[1]).filter(Boolean);
let bad = 0;
for (const f of process.argv.slice(2)) {
  const L = fs.readFileSync(f, 'utf8').split('\n'), err = [];
  const head = /^\[([A-Z_]+)\]$/.exec(L[0])?.[1];
  if (!TPL[head]) { console.log(`✗ ${f.split(/[\\/]/).pop()} · บรรทัดแรกไม่ใช่หัวชนิด ([PV_MODULE_STRUCTURE] ฯลฯ)`); bad++; continue; }
  const tk = keysOf(fs.readFileSync(new URL(`../${TPL[head]}`, import.meta.url), 'utf8'));
  const fk = keysOf(L.join('\n'));
  if (tk.join() !== fk.join()) err.push(`ชื่อ/ลำดับฟิลด์ไม่ตรงแม่แบบ (${fk.length}/${tk.length})`);
  // [ไม่ใช้กับเครื่องชนิดนี้] บรรทัดแรกใต้หัว section = ทั้ง section · เหนือบรรทัดค่า = เฉพาะฟิลด์นั้น
  let na = false, block = [], afterHead = false;
  let filled = 0, empty = 0;
  L.forEach((l, i) => {
    if (/^\[/.test(l)) { na = false; block = []; afterHead = true; return; }
    if (l.startsWith(';')) { if (l.includes('=')) err.push(`L${i + 1} คอมเมนต์มี =`); if (afterHead && /\[ไม่ใช้กับเครื่องชนิดนี้/.test(l)) na = true; afterHead = false; block.push(l); return; }
    afterHead = false;
    const m = /^([A-Za-z][A-Za-z0-9_]*) =( (.*))?$/.exec(l);
    if (!m) { if (l.trim()) err.push(`L${i + 1} รูปแบบผิด: ${l}`); block = []; return; }
    const [, k, , v] = m;
    if (v === undefined || v === '') { empty++; if (!na && !block.some((b) => /\[(ไม่มีข้อมูล|ไม่ใช้กับเครื่องชนิดนี้)/.test(b))) err.push(`L${i + 1} ${k} ว่างแต่ไม่มี [ไม่มีข้อมูล]`); }
    else {
      filled++;
      if (!/^(-?\d+(\.\d+)?|True|False|"[^";#]*")$/.test(v)) err.push(`L${i + 1} ${k} ค่าผิดรูปแบบ: ${v}`);
      if (!block.some((b) => b.startsWith('; [SRC:'))) err.push(`L${i + 1} ${k} ไม่มี [SRC]`);
      const e = ENUM[k]; if (e && !e.test(v.replace(/^"|"$/g, ''))) err.push(`L${i + 1} ${k} ไม่ตรงข้อ 11: ${v}`);
    }
    block = [];
  });
  console.log(`${err.length ? '✗' : '✓'} ${f.split('/').pop()} · กรอก ${filled} · ว่าง ${empty} · ฟิลด์ ${fk.length}`);
  for (const e of err) console.log('   ', e);
  bad += err.length;
}
process.exit(bad ? 1 : 0);
