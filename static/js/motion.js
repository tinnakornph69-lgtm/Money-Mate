/* ==========================================================================
   MoneyMate · motion.js
   ทำ 2 อย่างให้ "ทุกหน้า" โดยไม่ต้องแก้ไฟล์ pageN.html ทีละไฟล์
     1) Slide-in ตอนเข้าหน้า  — ส่วนหัว/การ์ดที่อยู่บนจอเลื่อนเข้ามาทีละชิ้น
     2) Scroll reveal          — ส่วนที่อยู่ล่างจอ จะเลื่อนขึ้นมาตอนเลื่อนลงไปถึง
   วิธีทำงาน: หา element ตาม selector ในตาราง RULES → ซ่อนไว้ (class mm-reveal)
              → IntersectionObserver เห็นเมื่อไหร่ก็เล่น animation แล้วปล่อยให้เป็นสไตล์เดิม
   ผู้ใช้ที่ตั้งค่า "ลดการเคลื่อนไหว" ในระบบ จะไม่เห็น animation เลย
   ========================================================================== */
(function () {
  'use strict';

  /* ---------- ไม่เล่นถ้าเบราว์เซอร์ไม่รองรับ / ผู้ใช้ขอลด motion ---------- */
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !('IntersectionObserver' in window) || !Element.prototype.animate) return;

  /* ---------- ค่าที่ปรับได้ ---------- */
  var EASE = 'cubic-bezier(.2,.72,.2,1)'; // เร็วตอนเริ่ม ช้าลงตอนจบ
  var DIST = 24;                           // ระยะสไลด์ซ้าย/ขวา (px)
  var RISE = 18;                           // ระยะเลื่อนขึ้น (px)
  var SHELL_ONCE = true;                   // true = header/sidebar สไลด์เข้าแค่ครั้งแรกของการเปิดเว็บ
                                           // false = สไลด์ทุกครั้งที่เปลี่ยนหน้า

  var isNarrow = window.matchMedia('(max-width: 720px)').matches;

  /* ถ้าเป็นการโหลดหน้าเดิมซ้ำ (เช่น กดบันทึกฟอร์มแล้วกลับมาหน้าเดิม) ให้เล่นเบาลง จะได้ไม่รำคาญ */
  var quick = false;
  try { quick = new URL(document.referrer).pathname === location.pathname; } catch (e) {}
  var K = quick ? 0.45 : 1;

  /* ---------- ตารางกติกา: [selector, ตัวเลือก] ----------
     x, y    = ระยะเริ่มต้น (px)   ลบ = มาจากซ้าย/บน   บวก = มาจากขวา/ล่าง
     s, r    = scale เริ่มต้น / องศาหมุนเริ่มต้น
     dur     = ความยาว (ms)        delay = หน่วงเพิ่ม (ms)
     inner   = ชิ้นย่อยที่อยู่ในการ์ด (แถวตาราง ฯลฯ) — เล่นซ้อนกับการ์ดได้
     bar     = แถบความคืบหน้า — ค่อย ๆ ไล่เต็มจากซ้ายไปขวา
     ตัวที่จับคู่ก่อนในตารางจะชนะ */
  var RULES = [
    ['.banner',                                                   { y: -18, dur: 500 }],

    /* ส่วนหัวของแต่ละหน้า: สไลด์เข้าจากซ้าย */
    ['.hero-box, .page-header, .si-hero, .if-hero, .account-profile-head, .dashboard-hero, .guide-hero',
                                                                  { x: -DIST, dur: 680 }],

    /* หน้าแรก (ยังไม่ล็อกอิน): ข้อความมาจากซ้าย น้อง Mate มาจากขวา */
    ['.public-copy',                                              { x: -DIST, dur: 720 }],
    ['.public-mate-zone',                                         { x: DIST, dur: 760, delay: 80 }],
    ['.public-feature',                                           { y: RISE, s: 0.985 }],
    ['.public-message-section',                                   { y: RISE, s: 0.99, dur: 700 }],
    ['.home-team > h2',                                           { y: 24 }],
    ['.home-team-member, .member',                                { y: RISE, s: 0.985 }],

    /* กล่องสรุปตัวเลขด้านบน: เด้งขึ้นมาทีละใบ */
    ['.dashboard-stat, .mm-dash-card, .mm3-summary > .mm3-card, .stat, .cards > .card',
                                                                  { y: RISE, s: 0.985 }],

    /* การ์ดหลัก: จะจัดคู่ซ้าย-ขวาให้ในฟังก์ชัน sideOf() ด้านล่าง; นอกนั้นเลื่อนขึ้น */
    ['.mm-panel, .mm3-card, .card, .panel, .si-card, .if-card, .dashboard-card, ' +
     '.account-info-card, .password-card, .goal-card, .auth-viewport, .guide-card, .guide-flow',
                                                                  { y: RISE, dur: 680 }],

    /* หน้าที่ไม่มีการ์ด (เช่น /team): หัวข้อและตารางที่อยู่ตรงใน main */
    ['main.wrap > h2, main.wrap > table, main.wrap > .table-wrap, main.wrap > .lead',
                                                                  { y: 26 }],

    /* วงกลม (pie) หมุนเข้ามา */
    ['.mm-pie',                                                   { y: 12, s: 0.96, dur: 720, inner: true }],

    /* ชิ้นย่อยในการ์ด: เลื่อนเข้าจากซ้ายทีละแถว */
    ['tbody tr, .recent-item, .mm-category-row, .mm-mini-row, .bar-row, .sum-row, .mm3-recurring-list > *',
                                                                  { x: -12, dur: 520, inner: true, max: 14 }],
    ['.quick-action',                                             { y: 10, s: 0.97, dur: 520, inner: true }],

    /* แถบความคืบหน้า */
    ['.bar-fill, .progress > div, .progress-bar, .progress-fill, .saving-mini-progress-fill',
                                                                  { bar: true, inner: true }]
  ];

  /* การ์ดที่อยู่ในกริด 2 คอลัมน์: ใบซ้ายมาจากซ้าย ใบขวามาจากขวา */
  var PAIR_PARENTS = '.mm-two, .grid-2, .dashboard-content-grid, .account-profile-info';

  function sideOf(el, o) {
    var parent = el.parentElement;
    if (!parent || !parent.matches(PAIR_PARENTS) || isNarrow) return o;
    var index = Array.prototype.indexOf.call(parent.children, el);
    var copy = {};
    for (var k in o) copy[k] = o[k];
    copy.y = 0;
    copy.x = index % 2 === 0 ? -DIST * 0.85 : DIST * 0.85;
    return copy;
  }

  /* ---------- 1) ติดป้าย (ซ่อน) element ตามตาราง ---------- */
  var info = new Map();      // element → ตัวเลือก
  var pending = new Set();   // element ที่ยังไม่ถูกเล่น

  RULES.forEach(function (rule) {
    var opts = rule[1];
    var count = new Map();   // นับจำนวนแถวต่อ parent เพื่อจำกัด max
    document.querySelectorAll(rule[0]).forEach(function (el) {
      if (info.has(el)) return;
      if (opts.max) {
        var n = (count.get(el.parentElement) || 0) + 1;
        count.set(el.parentElement, n);
        if (n > opts.max) return;
      }
      info.set(el, opts.inner ? opts : sideOf(el, opts));
    });
  });

  // ตัดชิ้นที่ซ้อนอยู่ในชิ้นใหญ่ที่ animate อยู่แล้วออก (ยกเว้นชิ้น inner)
  var all = Array.from(info.keys());
  all.forEach(function (el) {
    var o = info.get(el);
    if (o.inner) return;
    var p = el.parentElement;
    while (p) {
      var po = info.get(p);
      if (po && !po.inner) { info.delete(el); return; }
      p = p.parentElement;
    }
  });

  info.forEach(function (o, el) {
    el.classList.add(o.bar ? 'mm-bar-hide' : 'mm-reveal');
    pending.add(el);
  });

  /* ---------- 2) เล่น animation ---------- */
  function play(el, order) {
    var o = info.get(el);
    if (!o) return;
    pending.delete(el);
    el.classList.remove('mm-reveal', 'mm-bar-hide');

    // หน่วงเป็นทอด ๆ ให้ชิ้นที่ขึ้นพร้อมกันไม่ออกมาพร้อมกันหมด
    var step = o.inner ? 34 : 58;
    var cap = o.inner ? 320 : 280;
    var delay = ((o.inner ? 80 : 0) + Math.min(order * step, cap) + (o.delay || 0)) * K;

    if (o.bar) {
      el.animate(
        [{ clipPath: 'inset(0 100% 0 0)' }, { clipPath: 'inset(0 0 0 0)' }],
        { duration: 720 * (quick ? 0.6 : 1), delay: delay + 180, easing: EASE, fill: 'backwards' }
      );
      return;
    }

    var tf = 'translate3d(' + ((o.x || 0) * K) + 'px,' + ((o.y || 0) * K) + 'px,0)';
    if (o.s) tf += ' scale(' + o.s + ')';
    if (o.r) tf += ' rotate(' + o.r + 'deg)';

    // ใส่แค่ keyframe เริ่มต้น (offset: 0) — ปลายทางคือสไตล์เดิมของ element (กัน transform เดิมพัง)
    // ต้องใส่ offset: 0 เสมอ ไม่งั้นเบราว์เซอร์จะมองว่าเป็น keyframe "ปลายทาง" แล้วเล่นย้อนกลับ
    el.animate(
      [{ offset: 0, opacity: 0, transform: tf }],
      { duration: (o.dur || 750) * (quick ? 0.65 : 1), delay: delay, easing: EASE, fill: 'backwards' }
    );
  }

  function byPageOrder(a, b) {
    return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
  }

  function playBatch(list) {
    list.sort(byPageOrder);
    var blocks = 0, inners = 0;
    list.forEach(function (el) {
      var o = info.get(el);
      play(el, o && o.inner ? inners++ : blocks++);
    });
  }

  /* ---------- 3) Scroll reveal ---------- */
  var io = new IntersectionObserver(function (entries) {
    var batch = [];
    entries.forEach(function (e) {
      if (e.isIntersecting) { io.unobserve(e.target); batch.push(e.target); }
    });
    if (batch.length) playBatch(batch);
  }, {
    threshold: 0,                       // แค่โผล่เข้ามาก็เริ่ม (การ์ดที่สูงมากก็ไม่ค้าง)
    rootMargin: '0px 0px -8% 0px'       // รอให้ขึ้นมาเหนือขอบล่างจอนิดหนึ่งค่อยเล่น
  });
  pending.forEach(function (el) { io.observe(el); });

  /* กันหลุด: ถ้าเลื่อนสุดหน้าแล้ว หรือหน้าสั้นจนเลื่อนไม่ได้
     ชิ้นที่อยู่ในแถบขอบล่าง 8% จะไม่มีวันตัดกับ observer → เปิดให้เห็นเอง */
  var flushTimer = null;
  function flushIfAtBottom() {
    flushTimer = null;
    if (!pending.size) return;
    var atBottom = window.innerHeight + window.pageYOffset >= document.documentElement.scrollHeight - 4;
    if (!atBottom) return;
    var batch = [];
    pending.forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (r.height > 0 && r.top < window.innerHeight && r.bottom > 0) { io.unobserve(el); batch.push(el); }
    });
    if (batch.length) playBatch(batch);
  }
  function scheduleFlush() {
    if (flushTimer === null) flushTimer = setTimeout(flushIfAtBottom, 120);
  }
  window.addEventListener('scroll', scheduleFlush, { passive: true });
  window.addEventListener('resize', scheduleFlush);
  window.addEventListener('load', function () { setTimeout(flushIfAtBottom, 700); });

  /* ---------- 4) Header + Sidebar สไลด์เข้า (ครั้งแรกของการเปิดเว็บ) ---------- */
  function once(key, fn) {
    if (SHELL_ONCE) {
      try {
        if (sessionStorage.getItem(key)) return;
        sessionStorage.setItem(key, '1');
      } catch (e) { /* โหมดส่วนตัว: เล่นทุกครั้งก็ได้ */ }
    }
    fn();
  }

  var header = document.querySelector('.site-header');
  if (header) {
    once('mmShellHeader', function () {
      header.animate(
        [{ offset: 0, transform: 'translateY(-100%)', opacity: 0 }],
        { duration: 520, easing: EASE, fill: 'backwards' }
      );
    });
  }

  var sidebar = document.getElementById('mmSidebar');
  // บนจอเล็ก sidebar เป็นเมนูที่เลื่อนเปิดเอง จึงไม่แตะ
  if (sidebar && window.matchMedia('(min-width: 901px)').matches) {
    once('mmShellSide', function () {
      sidebar.animate(
        [{ offset: 0, transform: 'translateX(-100%)' }],
        { duration: 520, easing: EASE, fill: 'backwards' }
      );
      var items = sidebar.querySelectorAll('.mm-side-brand, .mm-sidenav > *, .mm-side-mate');
      Array.prototype.forEach.call(items, function (el, i) {
        el.animate(
          [{ offset: 0, opacity: 0, transform: 'translateX(-14px)' }],
          { duration: 500, delay: 180 + i * 48, easing: EASE, fill: 'backwards' }
        );
      });
    });
  }
})();
