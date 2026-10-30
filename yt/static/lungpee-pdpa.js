/* ============================================================================
 *  ProInventive — ลุงพี PDPA Consent Modal (Universal)
 *  Copyright (C) 2024-2569 ProInventive. All rights reserved.
 *
 *  PDPA Consent Modal ใช้ร่วมกันทุกโปรแกรมของ ProInventive
 *  รองรับ 3 ภาษา: ไทย / English / ລາວ
 *  ไม่พึ่ง CDN ภายนอก — ทำงานได้แบบ standalone
 *
 *  ใช้งาน: เพิ่ม <script src="path/to/lungpee-pdpa.js"></script> ใน <head>
 *  Debug:  window.LP_PDPA.reset()    → รีเซ็ต consent (reload)
 *          window.LP_PDPA.isOk()     → true/false
 * ========================================================================== */

(function () {
    'use strict';

    /* ─── config ─────────────────────────────────────────────── */
    var KEY  = 'lp_pdpa_v1';
    var VER  = '2569-10-30';  /* เปลี่ยนเมื่ออัปเดตเนื้อหา PDPA */
    var APP_NAME = (document.title || 'ProInventive').replace(/[—–·|:].*/,'').trim() ||
                  'ProInventive App';

    /* ─── text 3 ภาษา ─────────────────────────────────────────── */
    var L = {
        th: {
            tab: 'ไทย',
            title: 'นโยบายคุ้มครองข้อมูลส่วนบุคคล',
            sub: 'พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562',
            body: '<p><b>1. ผู้ควบคุมข้อมูล</b><br>' +
                  'บริษัท โปรอินเวนทีฟ จำกัด (ProInventive) เป็นผู้ควบคุมข้อมูลส่วนบุคคลสำหรับซอฟต์แวร์ทุกตัวในกลุ่ม ProInventive Suite รวมถึง <b>' + APP_NAME + '</b></p>' +
                  '<p><b>2. ข้อมูลที่เก็บรวบรวม</b><br>' +
                  'ระบบอาจเก็บ: ชื่อผู้ใช้, อีเมล, ข้อมูลการใช้งาน, ไฟล์ที่อัปโหลด, บันทึก Log เพื่อความปลอดภัย</p>' +
                  '<p><b>3. วัตถุประสงค์</b><br>' +
                  'ใช้ข้อมูลเพื่อ: การทำงานของระบบ, พัฒนาและปรับปรุงซอฟต์แวร์, จัดทำรายงาน ไม่มีการขายข้อมูลให้บุคคลที่สาม</p>' +
                  '<p><b>4. สิทธิ์ของท่าน</b><br>' +
                  'ท่านมีสิทธิ์ เข้าถึง · แก้ไข · ลบ · คัดค้าน · ถอนความยินยอม ข้อมูลของตนเองได้ทุกเมื่อ<br>' +
                  'ติดต่อ: <a href="mailto:giskku@gmail.com">giskku@gmail.com</a></p>' +
                  '<p class="lp-note">ซอฟต์แวร์นี้เป็นทรัพย์สินทางปัญญาของ ProInventive<br>' +
                  'Copyright &copy; 2024–2569 · ห้ามทำซ้ำหรือ reverse engineer โดยไม่ได้รับอนุญาต</p>',
            check: 'ข้าพเจ้าได้อ่านและยอมรับนโยบายนี้',
            btn: 'ยอมรับและใช้งาน'
        },
        en: {
            tab: 'English',
            title: 'Personal Data Protection Policy',
            sub: 'Thailand PDPA Act B.E. 2562 (2019)',
            body: '<p><b>1. Data Controller</b><br>' +
                  'ProInventive Co., Ltd. controls personal data for all ProInventive Suite software including <b>' + APP_NAME + '</b></p>' +
                  '<p><b>2. Data We Collect</b><br>' +
                  'The system may collect: username, email, usage data, uploaded files, access logs for security</p>' +
                  '<p><b>3. Purpose</b><br>' +
                  'Data is used for: system operation, software improvement, report generation. We never sell data to third parties.</p>' +
                  '<p><b>4. Your Rights</b><br>' +
                  'You have the right to: access, rectify, delete, object, or withdraw consent at any time.<br>' +
                  'Contact: <a href="mailto:giskku@gmail.com">giskku@gmail.com</a></p>' +
                  '<p class="lp-note">This software is the intellectual property of ProInventive.<br>' +
                  'Copyright &copy; 2024–2569 · Copying or reverse engineering without authorization is prohibited.</p>',
            check: 'I have read and accept this policy',
            btn: 'Accept & Continue'
        },
        lo: {
            tab: 'ລາວ',
            title: 'ນະໂຍບາຍຄຸ້ມຄອງຂໍ້ມູນສ່ວນຕົວ',
            sub: 'ກົດໝາຍ PDPA ໄທ ປີ ພ.ສ. 2562',
            body: '<p><b>1. ຜູ້ຄວບຄຸມຂໍ້ມູນ</b><br>' +
                  'ProInventive Co., Ltd. ຄວບຄຸມຂໍ້ມູນສ່ວນຕົວສຳລັບ <b>' + APP_NAME + '</b></p>' +
                  '<p><b>2. ຂໍ້ມູນທີ່ເກັບກຳ</b><br>' +
                  'ລະບົບອາດເກັບ: ຊື່ຜູ້ໃຊ້, ອີເມລ, ຂໍ້ມູນການໃຊ້, ໄຟລ໌ທີ່ອັບໂຫລດ, ບັນທຶກ Log</p>' +
                  '<p><b>3. ຈຸດປະສົງ</b><br>' +
                  'ໃຊ້ສຳລັບ: ການທຳງານລະບົບ, ພັດທະນາຊອຟແວລ໌, ຈັດທຳລາຍງານ</p>' +
                  '<p><b>4. ສິດຂອງທ່ານ</b><br>' +
                  'ທ່ານມີສິດ ເຂົ້າເຖິງ · ແກ້ໄຂ · ລຶບ · ຄັດຄ້ານ · ຖອນຄວາມຍິນຍອມ ໄດ້ທຸກເວລາ<br>' +
                  'ຕິດຕໍ່: <a href="mailto:giskku@gmail.com">giskku@gmail.com</a></p>' +
                  '<p class="lp-note">ຊອຟແວລ໌ນີ້ເປັນຊັບສິນຂອງ ProInventive · Copyright &copy; 2024–2569<br>' +
                  'ຫ້າມຄັດລອກ ຫຼື reverse engineer ໂດຍບໍ່ໄດ້ຮັບອະນຸຍາດ</p>',
            check: 'ຂ້າພະເຈົ້າໄດ້ອ່ານ ແລະ ຍອມຮັບ',
            btn: 'ຍອມຮັບ ແລະ ໃຊ້ງານ'
        }
    };

    /* ─── CSS (self-contained, no CDN) ───────────────────────── */
    var CSS = [
        '#lp-pdpa{position:fixed;inset:0;z-index:2147483647;background:rgba(0,0,0,.72);',
        'display:flex;align-items:center;justify-content:center;padding:1rem;',
        'font-family:Kanit,Sarabun,\'Noto Sans Thai\',system-ui,sans-serif;backdrop-filter:blur(3px)}',
        '#lp-box{background:#fff;border-radius:14px;width:100%;max-width:640px;',
        'max-height:90vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,.45);overflow:hidden}',
        '#lp-hd{padding:1.1rem 1.4rem .8rem;border-bottom:1px solid #e2e8f0;flex-shrink:0}',
        '#lp-hd .lp-brand{display:flex;align-items:center;gap:.5rem;margin-bottom:.6rem}',
        '#lp-hd .lp-brand b{font-size:.82rem;color:#1e293b}',
        '#lp-title{font-size:1.05rem;font-weight:700;color:#1e293b;margin:.1rem 0}',
        '#lp-sub{font-size:.76rem;color:#64748b;margin-bottom:.7rem}',
        '.lp-tabs{display:flex;gap:.2rem}',
        '.lp-tab{padding:.35rem .85rem;border-radius:7px 7px 0 0;font-size:.8rem;font-weight:600;',
        'cursor:pointer;border:none;background:transparent;color:#64748b;transition:.12s}',
        '.lp-tab.on{background:#2563eb;color:#fff}',
        '.lp-tab:hover:not(.on){background:#f1f5f9;color:#1e293b}',
        '#lp-body{flex:1;overflow-y:auto;padding:1.1rem 1.4rem;font-size:.85rem;',
        'color:#334155;line-height:1.75}',
        '#lp-body p{margin-bottom:.85rem}',
        '#lp-body a{color:#2563eb;text-decoration:underline}',
        '#lp-body .lp-note{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;',
        'padding:.55rem .85rem;font-size:.78rem;color:#92400e}',
        '#lp-ft{flex-shrink:0;padding:.9rem 1.4rem;border-top:1px solid #e2e8f0;background:#f8fafc}',
        '#lp-row{display:flex;align-items:flex-start;gap:.55rem;margin-bottom:.65rem;cursor:pointer}',
        '#lp-chk{width:15px;height:15px;margin-top:3px;cursor:pointer;flex-shrink:0;accent-color:#2563eb}',
        '#lp-lbl{font-size:.82rem;color:#475569;line-height:1.4}',
        '#lp-btn{width:100%;padding:.65rem;background:#2563eb;color:#fff;border:none;',
        'border-radius:9px;font-family:inherit;font-size:.88rem;font-weight:700;cursor:pointer;',
        'transition:.12s;box-shadow:0 3px 12px rgba(37,99,235,.35)}',
        '#lp-btn:disabled{background:#cbd5e1;box-shadow:none;cursor:not-allowed}',
        '#lp-btn:not(:disabled):hover{background:#1d4ed8}',
        '#lp-ver{font-size:.66rem;color:#94a3b8;text-align:right;margin-top:.4rem}',
        '@media(max-width:480px){#lp-box{border-radius:10px;max-height:95vh}',
        '#lp-body{padding:.85rem}}'
    ].join('');

    /* ─── helpers ─────────────────────────────────────────────── */
    function injectStyle() {
        var s = document.createElement('style');
        s.textContent = CSS;
        document.head.appendChild(s);
    }

    function needsConsent() {
        try { return sessionStorage.getItem(KEY) !== VER; } catch(e) { return true; }
    }

    function markAccepted() {
        try { sessionStorage.setItem(KEY, VER); } catch(e) {}
    }

    /* ─── build DOM ───────────────────────────────────────────── */
    function build(lang) {
        var d = L[lang];
        var tabs = Object.keys(L).map(function(k) {
            return '<button class="lp-tab' + (k===lang?' on':'') + '" data-l="'+k+'">'+L[k].tab+'</button>';
        }).join('');

        var el = document.createElement('div');
        el.id = 'lp-pdpa';
        el.setAttribute('role','dialog');
        el.setAttribute('aria-modal','true');
        el.innerHTML = '<div id="lp-box">' +
            '<div id="lp-hd">' +
              '<div class="lp-brand"><b>&#127968; ProInventive Suite</b></div>' +
              '<div id="lp-title">'+d.title+'</div>' +
              '<div id="lp-sub">'+d.sub+'</div>' +
              '<div class="lp-tabs">'+tabs+'</div>' +
            '</div>' +
            '<div id="lp-body">'+d.body+'</div>' +
            '<div id="lp-ft">' +
              '<label id="lp-row"><input type="checkbox" id="lp-chk"><span id="lp-lbl">'+d.check+'</span></label>' +
              '<button id="lp-btn" disabled>'+d.btn+'</button>' +
              '<div id="lp-ver">ProInventive Suite &middot; PDPA '+VER+'</div>' +
            '</div>' +
          '</div>';
        return el;
    }

    /* ─── switch tab ──────────────────────────────────────────── */
    function switchTab(lang, overlay) {
        var d = L[lang];
        overlay.querySelector('#lp-title').textContent = d.title;
        overlay.querySelector('#lp-sub').textContent = d.sub;
        overlay.querySelector('#lp-body').innerHTML = d.body;
        overlay.querySelector('#lp-lbl').textContent = d.check;
        overlay.querySelector('#lp-btn').textContent = d.btn;
        overlay.querySelectorAll('.lp-tab').forEach(function(t) {
            t.className = 'lp-tab' + (t.dataset.l === lang ? ' on' : '');
        });
        overlay.querySelector('#lp-chk').checked = false;
        overlay.querySelector('#lp-btn').disabled = true;
    }

    /* ─── init ────────────────────────────────────────────────── */
    function init() {
        if (!needsConsent()) return;

        injectStyle();

        var nav = navigator.language || '';
        var defLang = nav.startsWith('lo') ? 'lo' : nav.startsWith('en') ? 'en' : 'th';
        var overlay = build(defLang);
        document.body.appendChild(overlay);

        overlay.querySelectorAll('.lp-tab').forEach(function(btn) {
            btn.addEventListener('click', function() { switchTab(btn.dataset.l, overlay); });
        });

        overlay.querySelector('#lp-chk').addEventListener('change', function() {
            overlay.querySelector('#lp-btn').disabled = !this.checked;
        });

        overlay.querySelector('#lp-btn').addEventListener('click', function() {
            markAccepted();
            overlay.style.opacity = '0';
            overlay.style.transition = 'opacity .2s';
            setTimeout(function() { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 220);
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && document.getElementById('lp-pdpa')) e.preventDefault();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.LP_PDPA = {
        reset: function() { try { sessionStorage.removeItem(KEY); } catch(e){} location.reload(); },
        isOk:  function() { return !needsConsent(); }
    };

})();
