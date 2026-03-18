(() => {
const dom = window.DashboardDOM;
const {
  DATA, COLS, PERIODS, METRICS, COMPUTED_YI_COLS,
  TTMROE_IDX, TTMROIC_IDX, PCT_METRICS,
  parseNum, fmtYi, isMobile, getColUnit, getStockType,
} = window.DashboardShared;

/* ── Computed metric groups for card layout ── */
const CARD_GROUPS = [
  {
    title: '排名',
    color: '#c41e3a',
    items: [
      { label: '综合排名', idx: 39 },
      { label: '低估', idx: 34 },
      { label: '成长', idx: 35 },
      { label: '质量', idx: 36 },
      { label: '股东回报', idx: 37 },
    ],
  },
  {
    title: '估值',
    color: '#c41e3a',
    layout: '3col',
    items: [
      { label: 'PE(TTM)', idx: 6 },
      { label: 'PB', idx: 7 },
      { label: '股东收益率', idx: 32, unit: '%', tip: 'TTMFCF ÷ (总市值+净现金)\n即自由现金流收益率，越高越低估' },
    ],
  },
  {
    title: '盈利能力',
    color: '#16a34a',
    layout: '3col',
    items: [
      { label: 'TTM归母净利润', idx: 11, yi: true },
      { label: 'TTMROE', idx: TTMROE_IDX, unit: '%' },
      { label: 'TTMROIC', idx: TTMROIC_IDX, unit: '%' },
    ],
  },
  {
    title: '增长能力',
    color: '#059669',
    layout: '3col',
    dynamic: 'growth',
  },
  {
    title: '现金流',
    color: '#0891b2',
    items: [
      { label: 'TTMFCF', idx: 31, yi: true },
      { label: 'TTM经营现金流', idx: 21, yi: true },
      { label: 'TTM投资现金流', idx: 22, yi: true },
      { label: 'TTM资本支出', idx: 23, yi: true },
      { label: 'TTM融资现金流', idx: 24, yi: true },
    ],
  },
  {
    title: '资产负债',
    color: '#2563eb',
    items: [
      { label: '总市值', idx: 5, yi: true },
      { label: '净现金', idx: 29, yi: true },
      { label: '有息负债', idx: 30, yi: true },
      { label: '最新权益合计', idx: 18, yi: true },
    ],
  },
  {
    title: '分红回购',
    color: '#d97706',
    items: [
      { label: '预期25年度分红', idx: 27, yi: true },
      { label: '预期25股东回报', idx: 28, yi: true },
      { label: '股东回报分配率', idx: 33, unit: '%' },
      { label: 'TTM股份回购', idx: 25, yi: true },
    ],
  },
];

/* ── Format value for display ── */
function fmtVal(raw, spec) {
  if (raw === null || raw === undefined || raw === '--') return '--';
  if (spec && spec.yi) {
    const n = parseNum(String(raw));
    if (n === null) return String(raw);
    return fmtYi(n) + '亿';
  }
  if (spec && spec.unit === '%') {
    const n = parseNum(String(raw));
    if (n === null) return String(raw);
    return n.toFixed(1) + '%';
  }
  // Ranking / PE / PB — just show value
  const n = parseNum(String(raw));
  if (n === null) return String(raw);
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(1);
}

function valClass(raw) {
  const n = parseNum(String(raw));
  if (n === null) return '';
  if (n < 0) return ' neg';
  if (n > 0) return ' pos';
  return '';
}

/* ── Period data: build a metric → period lookup from COLS ── */
function buildPeriodIndex() {
  // Returns: { metricName: [ {period, idx}, ... ], ... }
  const map = {};
  COLS.forEach(col => {
    const pipe = col.fullName.indexOf('|');
    if (pipe < 0) return;
    const metric = col.fullName.slice(0, pipe);
    const period = col.fullName.slice(pipe + 1);
    if (!map[metric]) map[metric] = [];
    map[metric].push({ period, idx: col.idx });
  });
  return map;
}

const PERIOD_MAP = buildPeriodIndex();

/* ── Format period value ── */
function fmtPeriodVal(raw, metric) {
  if (raw === null || raw === undefined || raw === '--') return '--';
  const n = parseNum(String(raw));
  if (n === null) return String(raw);
  if (PCT_METRICS.has(metric)) return n.toFixed(1) + '%';
  return fmtYi(n) + '亿';
}

/* ── Build HTML ── */
function buildDetailHTML(row) {
  let html = '';

  // Card groups
  CARD_GROUPS.forEach(group => {
    html += `<div class="sd-section">`;
    html += `<h3 class="sd-section-title" style="border-left-color:${group.color}">${group.title}</h3>`;

    if (group.title === '排名') {
      const stockType = getStockType(row);
      html = html.replace(
        `>${group.title}</h3>`,
        `>${group.title} <span class="sd-section-sub">（${stockType}序列）</span></h3>`
      );
      html += '<div class="sd-ranks sd-ranks-5">';
      group.items.forEach(item => {
        const raw = row[item.idx];
        const display = fmtVal(raw, item);
        html += `<div class="sd-rank">
          <div class="sd-rank-label">${item.label}</div>
          <div class="sd-rank-value">${display}</div>
        </div>`;
      });
      html += '</div>';
    } else if (group.dynamic === 'growth') {
      // 增长能力: TTM净利同比 + 最近2个有数据报期的净利润同比
      const items = [];
      // TTM净利同比 (computed col idx 12)
      items.push({ label: 'TTM净利同比', raw: row[12], unit: '%' });
      // Find 2 most recent periods with data for 净利润同比 (entries ordered newest-first)
      const entries = PERIOD_MAP['净利润同比'] || [];
      let found = 0;
      for (let i = 0; i < entries.length && found < 2; i++) {
        const e = entries[i];
        const v = row[e.idx];
        if (v !== null && v !== undefined && v !== '--') {
          items.push({ label: e.period + '同比', raw: v, unit: '%' });
          found++;
        }
      }
      html += '<div class="sd-cards sd-cards-3">';
      items.forEach(item => {
        const display = fmtVal(item.raw, item);
        const cls = valClass(item.raw);
        html += `<div class="sd-card">
          <div class="sd-card-label">${item.label}</div>
          <div class="sd-card-value${cls}">${display}</div>
        </div>`;
      });
      html += '</div>';
    } else {
      const gridClass = group.layout === '3col' ? 'sd-cards sd-cards-3' : 'sd-cards';
      html += `<div class="${gridClass}">`;
      group.items.forEach(item => {
        const raw = row[item.idx];
        const display = fmtVal(raw, item);
        const cls = valClass(raw);
        const tipBtn = item.tip
          ? ` <button class="sd-tip-btn" data-tip="${item.tip.replace(/"/g, '&quot;')}">?</button>`
          : '';
        html += `<div class="sd-card">
          <div class="sd-card-label">${item.label}${tipBtn}</div>
          <div class="sd-card-value${cls}">${display}</div>
        </div>`;
      });
      html += '</div>';
    }
    html += '</div>';
  });

  // Period data as accordion
  html += '<div class="sd-section">';
  html += '<h3 class="sd-section-title" style="border-left-color:#7c3aed">历史报期数据</h3>';
  METRICS.forEach(metric => {
    const entries = PERIOD_MAP[metric];
    if (!entries || entries.length === 0) return;
    // Check if any data exists
    const hasData = entries.some(e => {
      const v = row[e.idx];
      return v !== null && v !== undefined && v !== '--';
    });
    html += `<div class="sd-period-group${hasData ? '' : ' sd-empty'}">`;
    html += `<div class="sd-period-hdr">${metric}</div>`;
    html += '<div class="sd-period-body">';
    entries.forEach(e => {
      const raw = row[e.idx];
      const display = fmtPeriodVal(raw, metric);
      const cls = valClass(raw);
      html += `<div class="sd-period-row">
        <span class="sd-period-label">${e.period}</span>
        <span class="sd-period-val${cls}">${display}</span>
      </div>`;
    });
    html += '</div></div>';
  });
  html += '</div>';

  return html;
}

/* ── Open / Close ── */
let isOpen = false;

function openDetail(dataIdx) {
  const row = DATA.rows[dataIdx];
  if (!row) return;

  // Header
  dom.sdCode.textContent = row[1] || '';
  dom.sdName.textContent = row[2] || '';
  dom.sdIndustry.textContent = row[9] || '';

  const price = row[3];
  dom.sdPrice.textContent = price != null ? String(price) : '--';

  const chg = parseNum(String(row[4]));
  if (chg !== null) {
    const sign = chg > 0 ? '+' : '';
    dom.sdChange.textContent = sign + chg.toFixed(2) + '%';
    dom.sdChange.className = 'sd-change' + (chg > 0 ? ' pos' : chg < 0 ? ' neg' : '');
  } else {
    dom.sdChange.textContent = '--';
    dom.sdChange.className = 'sd-change';
  }

  const mktcap = parseNum(String(row[5]));
  dom.sdMktcap.textContent = mktcap !== null ? '市值 ' + fmtYi(mktcap) + '亿' : '';

  // Body
  dom.sdBody.innerHTML = buildDetailHTML(row);

  // Accordion click
  dom.sdBody.querySelectorAll('.sd-period-hdr').forEach(hdr => {
    hdr.addEventListener('click', () => {
      hdr.parentElement.classList.toggle('open');
    });
  });

  // Tip popover click
  dom.sdBody.querySelectorAll('.sd-tip-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Remove any existing popover
      const old = dom.sdBody.querySelector('.sd-tip-pop');
      if (old) old.remove();
      // Create popover
      const pop = document.createElement('div');
      pop.className = 'sd-tip-pop';
      pop.textContent = btn.dataset.tip;
      btn.closest('.sd-card').appendChild(pop);
      // Auto dismiss
      const dismiss = () => { pop.remove(); document.removeEventListener('click', dismiss); };
      setTimeout(() => document.addEventListener('click', dismiss), 10);
    });
  });

  // Show
  dom.sdOverlay.classList.add('open');
  dom.sdModal.classList.add('open');
  dom.sdModal.classList.remove('closing');
  document.body.style.overflow = 'hidden';
  dom.sdBody.scrollTop = 0;
  isOpen = true;
}

function closeDetail() {
  if (!isOpen) return;
  isOpen = false;
  dom.sdModal.classList.add('closing');
  dom.sdModal.classList.remove('open');
  dom.sdOverlay.classList.remove('open');
  document.body.style.overflow = '';
  setTimeout(() => {
    dom.sdModal.classList.remove('closing');
  }, 300);
}

/* ── Swipe-to-dismiss ── */
let touchStartY = 0;
let touchCurrentY = 0;
let isDragging = false;

function onTouchStart(e) {
  // Only allow swipe on handle / header area
  const target = e.target;
  const isHandle = target.classList.contains('sd-handle') ||
    target.closest('.sd-header') ||
    target.classList.contains('sd-modal');
  // Also allow if body is scrolled to top
  const bodyAtTop = dom.sdBody.scrollTop <= 0;
  if (!isHandle && !bodyAtTop) return;

  touchStartY = e.touches[0].clientY;
  touchCurrentY = touchStartY;
  isDragging = true;
  dom.sdModal.style.transition = 'none';
}

function onTouchMove(e) {
  if (!isDragging) return;
  touchCurrentY = e.touches[0].clientY;
  const delta = touchCurrentY - touchStartY;
  if (delta < 0) return; // only downward
  dom.sdModal.style.transform = `translateY(${delta}px)`;
}

function onTouchEnd() {
  if (!isDragging) return;
  isDragging = false;
  dom.sdModal.style.transition = '';
  const delta = touchCurrentY - touchStartY;
  if (delta > 120) {
    closeDetail();
  } else {
    dom.sdModal.style.transform = '';
  }
}

/* ── Init ── */
function initStockDetail() {
  dom.sdClose.addEventListener('click', closeDetail);
  dom.sdOverlay.addEventListener('click', closeDetail);

  dom.sdModal.addEventListener('touchstart', onTouchStart, { passive: true });
  dom.sdModal.addEventListener('touchmove', onTouchMove, { passive: true });
  dom.sdModal.addEventListener('touchend', onTouchEnd, { passive: true });

  // Event delegation: tap stock name in table on mobile
  dom.tableBody.addEventListener('click', (e) => {
    if (!isMobile()) return;
    const td = e.target.closest('td[data-colidx="2"]');
    if (!td) return;
    const tr = td.closest('tr[data-row-index]');
    if (!tr) return;
    const displayIdx = parseInt(tr.dataset.rowIndex, 10);
    const { state } = window.DashboardState;
    const dataIdx = state.displayIndices[displayIdx];
    if (dataIdx !== undefined) openDetail(dataIdx);
  });
}

window.DashboardStockDetail = { openDetail, closeDetail, initStockDetail };
})();
