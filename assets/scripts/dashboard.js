const _d = window.STOCK_DATA;
const DATA    = {headers: _d.headers, rows: _d.rows};
const COLS    = _d.cols;
const PERIODS = _d.periods;
const METRICS = _d.metrics;
const ROIC_START = _d.roic_start;   // first ROIC period col
const ROIC_END   = _d.roic_end;     // last ROIC period col
const TTMROE_IDX  = _d.ttmroe_idx;  // computed TTMROE col
const TTMROIC_IDX = _d.ttmroic_idx; // computed TTMROIC col
// Inject dynamic content from data.js
document.getElementById('sTotalCount').textContent = _d.row_count;

// Percentage-type metrics — do NOT convert to 亿
const PCT_METRICS = new Set(['净利润同比', 'ROE', 'ROIC']);

const COMPUTED_YI_COLS = new Set(_d.computed_yi_cols);
const COMPUTED_COL_NAMES = _d.computed_col_names;
const FILTER_COLS = _d.filter_cols;

// ---- Utility ----
function parseNum(s) {
  if (s === null || s === undefined || s === '--') return null;
  s = String(s).replace(/,/g, '');
  let m = 1;
  if (s.endsWith('亿')) { m = 1e8; s = s.slice(0, -1); }
  else if (s.endsWith('万')) { m = 1e4; s = s.slice(0, -1); }
  const v = parseFloat(s);
  return isNaN(v) ? null : v * m;
}

function parseStrictNum(s) {
  if (s === null || s === undefined || s === '--') return null;
  s = String(s).replace(/,/g, '').trim();
  let m = 1;
  if (s.endsWith('亿')) { m = 1e8; s = s.slice(0, -1); }
  else if (s.endsWith('万')) { m = 1e4; s = s.slice(0, -1); }
  if (!/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(s)) return null;
  const v = parseFloat(s);
  return isNaN(v) ? null : v * m;
}

function fmtYi(n) {
  // Pure number in 亿 units — no unit suffix (unit shown in column header)
  const yi = n / 1e8;
  if (Math.abs(yi) >= 1) return yi.toFixed(1);
  return yi.toFixed(2);
}

function getColUnit(col) {
  if (col.idx === 5) return '亿';
  if (col.idx === 8) return '亿股';
  if (COMPUTED_YI_COLS.has(col.idx)) return '亿';
  if (col.idx === 12 || col.idx === TTMROE_IDX || col.idx === TTMROIC_IDX
      || col.idx === 32 || col.idx === 33) return '%';
  if (col.group !== '基本信息' && col.group !== '计算指标' && !PCT_METRICS.has(col.group)) return '亿';
  return '';
}

function fmtCell(val, col) {
  if (val === '--' || val === null || val === undefined) return '--';
  if (col.idx === 6 || col.idx === 7) {  // PE / PB
    const n = parseNum(String(val));
    return n === null ? val : n.toFixed(1);
  }
  if (col.idx === 10) return val;  // 最新财报季: text as-is
  if (col.idx === 12 || col.idx === TTMROE_IDX || col.idx === TTMROIC_IDX
      || col.idx === 32 || col.idx === 33) {  // % cols: 1 decimal
    const n = parseNum(String(val));
    return n === null ? val : n.toFixed(1);
  }
  if (!getColUnit(col)) return val;  // ranking/composite: return as-is
  const n = parseNum(String(val));
  if (n === null) return val;
  return fmtYi(n);
}

function fmtMktCap(v) {
  if (v === null) return '--';
  const yi = v / 1e8;
  const s = Math.abs(yi) >= 1 ? yi.toFixed(1) : yi.toFixed(2);
  return parseFloat(s).toLocaleString('zh-CN') + '亿';
}

function fmtNum(v) {
  if (v === null || v === undefined) return '--';
  return fmtYi(v) + '亿';   // summary bar keeps unit
}

// ---- Stock type classification ----
// 金融股: 行业 in {保险,其他金融,银行} OR (行业==综合企业 AND 名称含中信集团)
// 非金融股: 其余全部股票；是否能参与排名由字段完整度自然决定

function isJinRong(row) {
  const ind = String(row[9]);
  if (ind === '保险' || ind === '其他金融' || ind === '银行') return true;
  if (ind === '综合企业' && String(row[2]).includes('中信股份')) return true;
  return false;
}

function getStockType(row) {
  if (isJinRong(row)) return '金融股';
  return '非金融股';
}

// ---- State ----
const METRICS_DEFAULT_HIDDEN   = new Set(_d.metrics_hidden);
const COMPUTED_DEFAULT_HIDDEN  = new Set(_d.computed_hidden);
const FIXED_DEFAULT_HIDDEN     = new Set(_d.fixed_hidden || []);
const FIXED_TOGGLEABLE_NAMES   = COLS.filter(c => c.group === '基本信息' && !c.locked).map(c => c.name);
let sortCol = 39, sortDir = 'asc';   // 默认按综合排名升序
let visiblePeriods = new Set(PERIODS);
let visibleMetrics = new Set(METRICS.filter(m => !METRICS_DEFAULT_HIDDEN.has(m)));
let visibleComputedCols = new Set(COMPUTED_COL_NAMES.filter(n => !COMPUTED_DEFAULT_HIDDEN.has(n)));
let visibleFixedCols = new Set(FIXED_TOGGLEABLE_NAMES.filter(n => !FIXED_DEFAULT_HIDDEN.has(n)));
// Mobile detection & defaults
const isMobile = () => window.innerWidth < 768;
const MOBILE_COMPUTED_VISIBLE = new Set(['低估排名', '成长排名', '质量排名', '股东回报排名', '综合排名']);
if (isMobile()) {
  visibleMetrics      = new Set();                         // no period metrics
  visibleComputedCols = new Set(MOBILE_COMPUTED_VISIBLE);  // only rankings
  visibleFixedCols    = new Set(['股票代码']);               // show code column by default

  // Scroll boundary: rely on CSS overscroll-behavior:none + touch-action.
  // No JS passive:false handler — that blocks the render thread and causes jank.
}

let searchText = '';
let filterIndustry = '';
let filterStockType = '非金融股';   // 默认筛选非金融股
let filters = {};   // {colIdx: {op, val}}
let displayIndices = [];

// ---- Virtual Scroll State ----
const ROW_HEIGHT = 33;
const V_OVERSCAN = 20;
let renderStartIndex = 0;
let renderEndIndex = 50;

function resetVirtualScroll() {
  const wrap = document.querySelector('.table-wrap');
  wrap.scrollTop = 0;
  renderStartIndex = 0;
  renderEndIndex = 50;
}

document.querySelector('.table-wrap').addEventListener('scroll', () => {
  const wrap = document.querySelector('.table-wrap');
  const scrollTop = wrap.scrollTop;
  const viewportHeight = wrap.clientHeight;
  
  const newStart = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - V_OVERSCAN);
  const newEnd = Math.min(displayIndices.length, Math.ceil((scrollTop + viewportHeight) / ROW_HEIGHT) + V_OVERSCAN);
  
  if (newStart !== renderStartIndex || newEnd !== renderEndIndex) {
    renderStartIndex = newStart;
    renderEndIndex = newEnd;
    buildBody();
  }
});

// ---- Computed col groups (for col picker) ----
const COMPUTED_GROUPS = [
  { label: '盈利', cols: ['TTM归母净利润', 'TTM净利同比'] },
  { label: '回报率', cols: ['TTMROE', 'TTMROIC', '股东收益率', '股东回报分配率'] },
  { label: '现金流', cols: ['TTM经营现金流', 'TTM投资现金流', 'TTM资本支出', 'TTM融资现金流', 'TTMFCF'] },
  { label: '资产负债', cols: ['最新总现金', '最新流动资产', '最新总负债', '最新短期借款', '最新长期借款', '最新权益合计', '净现金', '有息负债'] },
  { label: '分红回购', cols: ['TTM股份回购', 'TTM支付股息', '预期25年度分红', '预期25股东回报'] },
  { label: '排名', cols: ['低估排名', '成长排名', '质量排名', '股东回报排名', '综合分数', '综合排名'] },
];

// ---- Column picker (2-D: periods × metrics) ----
function buildColPicker() {
  const body = document.getElementById('cpBody');

  function makeSection(title, items, activeSet) {
    let html = `<div class="cp-group">
      <div class="cp-group-hdr">
        <span class="cp-group-name">${title}</span>
        <button class="cp-group-btn" data-sec="${title}" data-a="all">全选</button>
        <button class="cp-group-btn" data-sec="${title}" data-a="none">全不选</button>
      </div><div class="cp-cols">`;
    items.forEach(item => {
      const chk = activeSet.has(item) ? 'checked' : '';
      html += `<label class="cp-col"><input type="checkbox" data-sec="${title}" data-val="${item}" ${chk}> ${item}</label>`;
    });
    html += `</div></div>`;
    return html;
  }

  // Computed cols section — grouped by category
  function makeComputedSection() {
    let h = `<div class="cp-group"><div class="cp-group-hdr">
      <span class="cp-group-name">计算指标</span>
      <button class="cp-group-btn" data-sec="computed" data-a="all">全选</button>
      <button class="cp-group-btn" data-sec="computed" data-a="none">全不选</button>
      </div><div class="cp-cols">`;
    COMPUTED_GROUPS.forEach(grp => {
      h += `<span class="cp-sublabel">${grp.label}</span>`;
      grp.cols.forEach(n => {
        h += `<label class="cp-col"><input type="checkbox" data-sec="computed" data-val="${n}" ${visibleComputedCols.has(n)?'checked':''}> ${n}</label>`;
      });
    });
    return h + `</div></div>`;
  }

  function makeFixedSection() {
    const codeColName = isMobile() ? (COLS.find(c => c.idx === 1)?.name) : null;
    if (!FIXED_TOGGLEABLE_NAMES.length && !codeColName) return '';
    let h = `<div class="cp-group"><div class="cp-group-hdr">
      <span class="cp-group-name">基本信息</span>
      <button class="cp-group-btn" data-sec="fixed" data-a="all">全选</button>
      <button class="cp-group-btn" data-sec="fixed" data-a="none">全不选</button>
      </div><div class="cp-cols">`;
    // Mobile: 代码列是 locked 不在默认列表，但手机端允许用户手动勾选
    if (codeColName) {
      h += `<label class="cp-col"><input type="checkbox" data-sec="fixed" data-val="${codeColName}" ${visibleFixedCols.has(codeColName)?'checked':''}> ${codeColName}</label>`;
    }
    FIXED_TOGGLEABLE_NAMES.forEach(n => {
      h += `<label class="cp-col"><input type="checkbox" data-sec="fixed" data-val="${n}" ${visibleFixedCols.has(n)?'checked':''}> ${n}</label>`;
    });
    // 最新财报季 is computed but displayed under 基本信息
    h += `<label class="cp-col"><input type="checkbox" data-sec="computed" data-val="最新财报季" ${visibleComputedCols.has('最新财报季')?'checked':''}> 最新财报季</label>`;
    return h + `</div></div>`;
  }

  body.innerHTML =
    makeFixedSection() +
    makeComputedSection() +
    makeSection('财报周期', PERIODS, visiblePeriods) +
    makeSection('财务指标', METRICS, visibleMetrics);

  body.querySelectorAll('input[data-sec]').forEach(cb => {
    cb.addEventListener('change', e => {
      const sec = e.target.dataset.sec;
      const set = sec === 'fixed'    ? visibleFixedCols
                : sec === 'computed' ? visibleComputedCols
                : sec === '财报周期' ? visiblePeriods : visibleMetrics;
      if (e.target.checked) set.add(e.target.dataset.val);
      else set.delete(e.target.dataset.val);
      buildHeader(); buildBody();
    });
  });

  body.querySelectorAll('.cp-group-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      const sec = e.target.dataset.sec;
      const set  = sec === 'computed' ? visibleComputedCols
                 : sec === '财报周期' ? visiblePeriods : visibleMetrics;
      const items = sec === 'fixed'    ? FIXED_TOGGLEABLE_NAMES
                  : sec === 'computed' ? COMPUTED_COL_NAMES
                  : sec === '财报周期' ? PERIODS : METRICS;
      if (e.target.dataset.a === 'all') items.forEach(v => set.add(v));
      else set.clear();
      buildColPicker(); buildHeader(); buildBody();
    });
  });
}

function openColPicker() {
  document.getElementById('colPicker').classList.add('open');
  document.getElementById('cpOverlay').classList.add('open');
  document.getElementById('colPickerBtn').classList.add('active');
  buildColPicker();
}

function closeColPicker() {
  document.getElementById('colPicker').classList.remove('open');
  document.getElementById('cpOverlay').classList.remove('open');
  document.getElementById('colPickerBtn').classList.remove('active');
}

document.getElementById('colPickerBtn').addEventListener('click', () => {
  if (document.getElementById('colPicker').classList.contains('open')) closeColPicker();
  else openColPicker();
});
document.getElementById('cpClose').addEventListener('click', closeColPicker);
document.getElementById('cpOverlay').addEventListener('click', closeColPicker);

// ---- Visible col defs ----
function getVisibleColDefs() {
  return COLS.filter(col => {
    if (col.idx === 0) return false;                                       // 序号列已移除
    if (isMobile() && col.idx === 1) return visibleFixedCols.has(col.name); // 代码列手机端可选
    if (col.locked) return true;
    if (col.group === '基本信息') return visibleFixedCols.has(col.name);
    if (col.group === '计算指标') return visibleComputedCols.has(col.name);
    const pipe = col.fullName.indexOf('|');
    const period = col.fullName.slice(pipe + 1);
    return visibleMetrics.has(col.group) && visiblePeriods.has(period);
  });
}

// ---- Clean column display name ----
function cleanColName(name) {
  const aliases = {
    '市盈率(pe,ttm)': 'TTMPE',
    '市净率(pb)':     'PB',
    '最新涨跌幅(%)':  '涨跌幅',
  };
  if (aliases[name]) return aliases[name];
  // Strip any parenthesized unit suffix, e.g. "(港元)", "(股)"
  return name.replace(/[（(][^）)]*[）)]/g, '').trim();
}

function isRankMetricName(name) {
  return name.endsWith('排名') || name === '综合分数';
}

function isActiveColumn(colidx) {
  return String(sortCol) === String(colidx);
}

function isRankColumn(col) {
  return isRankMetricName(cleanColName(col.name));
}

function isHighlightEligibleRankColumn(col) {
  return isRankColumn(col);
}

// ---- Build header ----
function buildHeader() {
  const thead = document.getElementById('tableHead');
  thead.innerHTML = '';
  const colDefs = getVisibleColDefs();
  const headerUnitOverride = {3: '港元', 4: '%'};
  
  if (!isMobile()) {
    const tr = document.createElement('tr');
    let prevGroup = null;
    colDefs.forEach(col => {
      const th = document.createElement('th');
      let metric, date;
      const pipe = col.fullName.indexOf('|');
      if (pipe >= 0) {
        metric = col.fullName.slice(0, pipe);
        date = col.fullName.slice(pipe + 1);
      } else {
        metric = cleanColName(col.name); date = '';
      }
      const unit = headerUnitOverride[col.idx] ?? getColUnit(col);
      const unitHtml = unit ? `<span class="th-unit">${unit}</span>` : '';
      th.innerHTML = `<span class="th-metric">${metric}</span>${unitHtml}${date ? `<span class="th-date">${date}</span>` : ''}`;
      th.dataset.colidx = col.idx;
      th.dataset.group = col.group;
      if (col.group !== prevGroup) { th.classList.add('group-start'); prevGroup = col.group; }
      if (String(sortCol) === String(col.idx)) {
        th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      }
      if (isActiveColumn(col.idx)) th.classList.add('active-col');
      th.addEventListener('click', () => onSortClick(col.idx));
      tr.appendChild(th);
    });
    thead.appendChild(tr);
  } else {
    const tr1 = document.createElement('tr');
    const tr2 = document.createElement('tr');
    let rankStartIdx = -1, rankCount = 0;
    colDefs.forEach((col, i) => {
      const m = cleanColName(col.name);
      if (m.endsWith('排名') || m === '综合分数') {
        if (rankStartIdx === -1) rankStartIdx = i;
        rankCount++;
      }
    });

    colDefs.forEach((col, i) => {
      const th = document.createElement('th');
      th.dataset.colidx = col.idx;
      if (String(sortCol) === String(col.idx)) {
        th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      }
      if (isActiveColumn(col.idx)) th.classList.add('active-col');
      th.addEventListener('click', () => onSortClick(col.idx));

      const metric = cleanColName(col.name);
      const isRank = isRankMetricName(metric);

      if (isRank) {
        if (i === rankStartIdx) {
          const gth = document.createElement('th');
          gth.textContent = '排名维度';
          gth.colSpan = rankCount;
          gth.classList.add('rank-band');
          if (colDefs.some(c => isRankColumn(c) && isActiveColumn(c.idx))) gth.classList.add('active-col');
          tr1.appendChild(gth);
        }
        th.innerHTML = `<span class="th-metric">${metric.replace('排名','')}</span>`;
        th.style.top = '22px';
        th.style.height = '24px';
        th.style.position = 'sticky';
        th.style.left = 'auto'; // Explicitly prevent accidental sticky left from previous selectors
        tr2.appendChild(th);
      } else {
        th.rowSpan = 2;
        const pipe = col.fullName.indexOf('|');
        let m, d;
        if (pipe >= 0) { m = col.fullName.slice(0, pipe); d = col.fullName.slice(pipe + 1); }
        else { m = metric; d = ''; }
        const unit = headerUnitOverride[col.idx] ?? getColUnit(col);
        const unitHtml = unit ? `<span class="th-unit">${unit}</span>` : '';
        th.innerHTML = `<span class="th-metric">${m}</span>${unitHtml}${d ? `<span class="th-date">${d}</span>` : ''}`;
        tr1.appendChild(th);
      }
    });
    thead.appendChild(tr1);
    thead.appendChild(tr2);
  }
  
  if (isMobile()) {
    document.getElementById('mainTable').classList.toggle(
      'table-has-code', getVisibleColDefs().some(c => c.idx === 1)
    );
  }
}

// ---- Build body ----
function buildBody() {
  const colDefs = getVisibleColDefs();
  let html = '';
  const totalRows = displayIndices.length;
  
  if (totalRows === 0) {
    document.getElementById('tableBody').innerHTML = '';
    return;
  }
  
  const topSpacerHeight = renderStartIndex * ROW_HEIGHT;
  const bottomSpacerHeight = (totalRows - renderEndIndex) * ROW_HEIGHT;
  
  if (topSpacerHeight > 0) {
    html += `<tr style="height: ${topSpacerHeight}px; background: transparent;"><td colspan="${colDefs.length}" style="padding: 0; border: none;"></td></tr>`;
  }

  for (let i = renderStartIndex; i < renderEndIndex; i++) {
    if (i >= totalRows) break;
    const ri = displayIndices[i];
    const row = DATA.rows[ri];
    html += `<tr>`;
    colDefs.forEach((col, pos) => {
      const rawVal = row[col.idx] ?? '--';
      const classes = [];
      if (isActiveColumn(col.idx)) classes.push('active-col');
      if (!col.locked) {
        const n = parseStrictNum(String(rawVal));
        if (n !== null) {
          if (isActiveColumn(col.idx) && isHighlightEligibleRankColumn(col)) classes.push('active-numeric');
          if (n < 0) classes.push('neg');
          else if (n > 0 && col.idx >= 4) classes.push('pos');
        }
      }
      const cls = classes.length ? ` class="${classes.join(' ')}"` : '';
      html += `<td${cls} data-colidx="${col.idx}">${fmtCell(rawVal, col)}</td>`;
    });
    html += '</tr>';
  }

  if (bottomSpacerHeight > 0) {
    html += `<tr style="height: ${bottomSpacerHeight}px; background: transparent;"><td colspan="${colDefs.length}" style="padding: 0; border: none;"></td></tr>`;
  }
  
  document.getElementById('tableBody').innerHTML = html;
}

function updateIndustryFilter() {
  const select = document.getElementById('industryFilter');
  select.innerHTML = '<option value="">所有行业</option>';
  
  const industries = new Set();
  DATA.rows.forEach(r => {
    if (getStockType(r) === filterStockType && r[9]) {
      industries.add(r[9]);
    }
  });
  
  Array.from(industries).sort().forEach(ind => {
    const opt = document.createElement('option');
    opt.value = ind;
    opt.textContent = ind;
    select.appendChild(opt);
  });
  
  if (industries.has(filterIndustry)) {
    select.value = filterIndustry;
  } else {
    filterIndustry = '';
    select.value = '';
  }
}

// ---- Filter & Sort ----
function applyFilters() {
  let indices = DATA.rows.map((_, i) => i);
  if (filterStockType) indices = indices.filter(i => getStockType(DATA.rows[i]) === filterStockType);
  document.getElementById('sTotalCount').textContent = indices.length; // Set base count before other filters
  
  if (filterIndustry) indices = indices.filter(i => DATA.rows[i][9] === filterIndustry);
  if (searchText) {
    const t = searchText.toLowerCase();
    indices = indices.filter(i =>
      String(DATA.rows[i][1]).toLowerCase().includes(t) ||
      String(DATA.rows[i][2]).toLowerCase().includes(t)
    );
  }
  // Computed column filters
  Object.entries(filters).forEach(([idx, f]) => {
    const ci = parseInt(idx);
    const fc = FILTER_COLS.find(c => c.idx === ci);
    const threshold = (fc?.isYi && f.val !== null) ? f.val * 1e8 : f.val;
    indices = indices.filter(i => {
      const v = parseNum(String(DATA.rows[i][ci]));
      if (f.op === 'empty') return v === null;
      if (v === null) return false;
      if (f.op === '>')  return v > threshold;
      if (f.op === '>=') return v >= threshold;
      if (f.op === '<')  return v < threshold;
      if (f.op === '<=') return v <= threshold;
      if (f.op === '=')  return v === threshold;
      return true;
    });
  });
  if (sortCol !== -1) {
    indices.sort((a, b) => {
      const ci = parseInt(sortCol);
      const va = parseNum(String(DATA.rows[a][ci]));
      const vb = parseNum(String(DATA.rows[b][ci]));
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      return sortDir === 'asc' ? va - vb : vb - va;
    });
  } else {
    // Default: sort by stock code ascending
    indices.sort((a, b) => String(DATA.rows[a][1]).localeCompare(String(DATA.rows[b][1])));
  }
  displayIndices = indices;
}

function onSortClick(colidx) {
  const ci = String(colidx);
  if (String(sortCol) === ci) {
    sortDir = sortDir === 'asc' ? 'desc' : 'asc';
  } else {
    sortCol = colidx;
    // Default to 'asc' for rankings, 'desc' for everything else
    const col = COLS.find(c => String(c.idx) === ci);
    const metric = col ? cleanColName(col.name) : '';
    const isRank = isRankMetricName(metric);
    sortDir = isRank ? 'asc' : 'desc';
  }
  applyFilters();
  buildHeader();
  buildBody();
  updateSummary();
}

// ---- Summary ----
function updateSummary() {
  document.getElementById('sRowCount').textContent = displayIndices.length;
}

// ---- Export Excel ----
function exportExcel() {
  const colDefs = getVisibleColDefs();

  // Header row: "指标 (单位) [周期]"
  const headerRow = colDefs.map(col => {
    const pipe = col.fullName.indexOf('|');
    const name = pipe >= 0 ? col.fullName.slice(0, pipe) : col.name;
    const date = pipe >= 0 ? col.fullName.slice(pipe + 1) : '';
    const unit = getColUnit(col);
    return name + (unit ? ` (${unit})` : '') + (date ? ` [${date}]` : '');
  });

  // Data rows: numbers as numeric, text as string
  const dataRows = displayIndices.map((ri, rowPos) => {
    const row = DATA.rows[ri];
    return colDefs.map((col, pos) => {
      if (col.idx === 0) return rowPos + 1;
      const rawVal = row[col.idx] ?? '--';
      const display = fmtCell(rawVal, col);
      if (display === '--' || display === '') return '';
      const n = parseFloat(display);
      return isNaN(n) ? display : n;
    });
  });

  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet([headerRow, ...dataRows]);
  XLSX.utils.book_append_sheet(wb, ws, '港股数据');
  XLSX.writeFile(wb, '港股数据.xlsx');
}

// ---- Filter panel ----
let pendingFilters = {};  // staged, applied on confirm

function openFilterPanel() {
  pendingFilters = Object.assign({}, filters);
  // populate metric dropdown
  const sel = document.getElementById('fpCol');
  sel.innerHTML = '<option value="">选择指标…</option>';
  FILTER_COLS.forEach(fc => {
    const unit = fc.unit ? ` (${fc.unit})` : '';
    sel.innerHTML += `<option value="${fc.idx}">${fc.name}${unit}</option>`;
  });
  sel.value = '';
  document.getElementById('fpOp').disabled = true;
  document.getElementById('fpVal').disabled = true;
  document.getElementById('fpVal').value = '';
  document.getElementById('fpUnit').textContent = '';
  document.getElementById('fpAddBtn').disabled = true;
  renderFilterChips();
  document.getElementById('filterPanel').classList.add('open');
  document.getElementById('filterOverlay').classList.add('open');
}

function closeFilterPanel() {
  document.getElementById('filterPanel').classList.remove('open');
  document.getElementById('filterOverlay').classList.remove('open');
}

function renderFilterChips() {
  const container = document.getElementById('fpActive');
  const entries = Object.entries(pendingFilters);
  if (!entries.length) {
    container.innerHTML = '<span class="fp-empty">暂无筛选条件</span>';
    return;
  }
  container.innerHTML = entries.map(([idx, f]) => {
    const fc = FILTER_COLS.find(c => c.idx === parseInt(idx));
    const opLabel = f.op === 'empty' ? '为空' : f.op;
    const valText = f.op === 'empty' ? '' : f.val + (fc?.unit || '');
    return `<span class="fp-chip">${fc?.name} ${opLabel} ${valText}<button class="fp-chip-rm" data-fidx="${idx}">×</button></span>`;
  }).join('');
  container.querySelectorAll('.fp-chip-rm').forEach(btn => {
    btn.addEventListener('click', () => {
      delete pendingFilters[btn.dataset.fidx];
      renderFilterChips();
    });
  });
}

document.getElementById('fpCol').addEventListener('change', () => {
  const idx = document.getElementById('fpCol').value;
  const fc = FILTER_COLS.find(c => c.idx === parseInt(idx));
  const has = !!idx;
  document.getElementById('fpOp').disabled = !has;
  document.getElementById('fpVal').disabled = !has;
  document.getElementById('fpVal').value = '';
  document.getElementById('fpUnit').textContent = fc?.unit || '';
  document.getElementById('fpAddBtn').disabled = !has;
});

document.getElementById('fpOp').addEventListener('change', () => {
  const op = document.getElementById('fpOp').value;
  document.getElementById('fpVal').disabled = (op === 'empty');
  if (op === 'empty') document.getElementById('fpVal').value = '';
});

document.getElementById('fpAddBtn').addEventListener('click', () => {
  const idx = parseInt(document.getElementById('fpCol').value);
  const op = document.getElementById('fpOp').value;
  const val = op === 'empty' ? null : parseFloat(document.getElementById('fpVal').value);
  if (!idx || !op || (op !== 'empty' && isNaN(val))) return;
  pendingFilters[idx] = {op, val};
  renderFilterChips();
  document.getElementById('fpCol').value = '';
  document.getElementById('fpOp').disabled = true;
  document.getElementById('fpVal').disabled = true;
  document.getElementById('fpVal').value = '';
  document.getElementById('fpUnit').textContent = '';
  document.getElementById('fpAddBtn').disabled = true;
});

document.getElementById('fpClearBtn').addEventListener('click', () => {
  pendingFilters = {};
  renderFilterChips();
});

document.getElementById('fpApplyBtn').addEventListener('click', () => {
  filters = Object.assign({}, pendingFilters);
  updateFilterToggleStyle();
  closeFilterPanel();
  render();
});

document.getElementById('filterClose').addEventListener('click', closeFilterPanel);
document.getElementById('filterOverlay').addEventListener('click', closeFilterPanel);

function updateFilterToggleStyle() {
  const btn = document.getElementById('filterToggleBtn');
  const hasActive = Object.keys(filters).length > 0;
  btn.classList.toggle('filter-active', hasActive);
  btn.textContent = hasActive ? '筛选 ●' : '筛选 ▼';
}

function updateURLState() {
  const params = new URLSearchParams();
  if (sortCol !== 39) params.set('sortCol', sortCol);
  if (sortDir !== 'asc') params.set('sortDir', sortDir);
  if (searchText) params.set('q', searchText);
  if (filterIndustry) params.set('ind', filterIndustry);
  if (filterStockType) params.set('type', filterStockType);
  if (Object.keys(filters).length > 0) params.set('f', JSON.stringify(filters));
  
  const qs = params.toString();
  const newUrl = window.location.pathname + (qs ? '?' + qs : '');
  window.history.replaceState(null, '', newUrl);
}

function render(resetScroll = true) {
  if (resetScroll) resetVirtualScroll();
  updateIndustryFilter();
  applyFilters();
  buildHeader();
  buildBody();
  updateSummary();
  updateURLState();
}

// ---- Events ----
document.getElementById('searchBox').addEventListener('input', e => {
  searchText = e.target.value.trim();
  render();
});

document.querySelectorAll('.queue-btn').forEach(btn => {
  btn.addEventListener('click', e => {
    document.querySelectorAll('.queue-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    filterStockType = e.target.getAttribute('data-type');
    filterIndustry = ''; // Reset industry filter when changing queue
    document.getElementById('industryFilter').value = '';
    render();
  });
});

document.getElementById('industryFilter').addEventListener('change', e => {
  filterIndustry = e.target.value;
  render();
});

document.getElementById('filterToggleBtn').addEventListener('click', () => {
  if (document.getElementById('filterPanel').classList.contains('open')) closeFilterPanel();
  else openFilterPanel();
});

document.getElementById('resetView').addEventListener('click', () => {
  sortCol = 39; sortDir = 'asc';
  searchText = ''; filterIndustry = ''; filterStockType = '非金融股';
  filters = {}; pendingFilters = {};
  document.getElementById('searchBox').value = '';
  document.getElementById('industryFilter').value = '';
  document.querySelectorAll('.queue-btn').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-type') === '非金融股');
  });
  if (isMobile()) {
    visibleMetrics      = new Set();
    visibleComputedCols = new Set(MOBILE_COMPUTED_VISIBLE);
    visibleFixedCols    = new Set(['股票代码']);
  } else {
    visiblePeriods      = new Set(PERIODS);
    visibleMetrics      = new Set(METRICS.filter(m => !METRICS_DEFAULT_HIDDEN.has(m)));
    visibleComputedCols = new Set(COMPUTED_COL_NAMES.filter(n => !COMPUTED_DEFAULT_HIDDEN.has(n)));
    visibleFixedCols    = new Set(FIXED_TOGGLEABLE_NAMES.filter(n => !FIXED_DEFAULT_HIDDEN.has(n)));
  }
  closeFilterPanel();
  updateFilterToggleStyle();
  closeColPicker();
  render();
});

document.getElementById('exportBtn').addEventListener('click', exportExcel);

document.getElementById('rulesBtn').addEventListener('click', () => {
  document.getElementById('rulesModal').classList.add('open');
  document.getElementById('rulesOverlay').classList.add('open');
});
function closeRules() {
  document.getElementById('rulesModal').classList.remove('open');
  document.getElementById('rulesOverlay').classList.remove('open');
}
document.getElementById('rulesClose').addEventListener('click', closeRules);
document.getElementById('rulesOverlay').addEventListener('click', closeRules);

// ---- Init ----
const params = new URLSearchParams(window.location.search);
if (params.has('sortCol')) sortCol = parseInt(params.get('sortCol'));
if (params.has('sortDir')) sortDir = params.get('sortDir');
if (params.has('q')) searchText = params.get('q');
if (params.has('ind')) filterIndustry = params.get('ind');
if (params.has('type')) filterStockType = params.get('type');
if (params.has('f')) {
  try { filters = JSON.parse(params.get('f')); } catch(e) {}
}

if (window.STOCK_DATA && window.STOCK_DATA.update_time) {
  const updateTime = document.getElementById('updateTime');
  if (updateTime) updateTime.innerText = window.STOCK_DATA.update_time;
  const heroTime = document.getElementById('heroUpdateTime');
  if (heroTime) heroTime.innerText = window.STOCK_DATA.update_time;
}
document.querySelectorAll('.queue-btn').forEach(b => b.classList.remove('active'));
const activeBtn = document.querySelector(`.queue-btn[data-type="${filterStockType}"]`) || document.getElementById('btnQueueFei');
activeBtn.classList.add('active');
filterStockType = activeBtn.getAttribute('data-type');
document.getElementById('industryFilter').value = filterIndustry;
document.getElementById('searchBox').value = searchText;
render();
