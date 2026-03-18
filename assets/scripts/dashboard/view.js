(() => {
const dom = window.DashboardDOM;
const {
  DATA,
  COLS,
  PCT_METRICS,
  TTMROE_IDX,
  TTMROIC_IDX,
  getColUnit,
  fmtCell,
  parseNum,
  parseStrictNum,
  isMobile,
} = window.DashboardShared;
const { state } = window.DashboardState;

const HEADER_UNIT_OVERRIDE = { 3: '港元', 4: '%' };

function cleanColName(name) {
  const aliases = {
    '市盈率(pe,ttm)': 'TTMPE',
    '市净率(pb)': 'PB',
    '最新涨跌幅(%)': '涨跌幅',
  };
  if (aliases[name]) return aliases[name];
  return name.replace(/[（(][^）)]*[）)]/g, '').trim();
}

function isRankMetricName(name) {
  return name.endsWith('排名') || name === '综合分数';
}

function isActiveColumn(colIdx) {
  return String(state.sortCol) === String(colIdx);
}

function isRankColumn(col) {
  return isRankMetricName(cleanColName(col.name));
}

function isHighlightEligibleRankColumn(col) {
  return isRankColumn(col);
}

function getVisibleColDefs() {
  return COLS.filter(col => {
    if (col.idx === 0) return false;
    if (isMobile() && col.idx === 1) return state.visibleFixedCols.has(col.name);
    if (col.locked) return true;
    if (col.group === '基本信息') return state.visibleFixedCols.has(col.name);
    if (col.group === '计算指标') return state.visibleComputedCols.has(col.name);
    const pipeIndex = col.fullName.indexOf('|');
    const period = col.fullName.slice(pipeIndex + 1);
    return state.visibleMetrics.has(col.group) && state.visiblePeriods.has(period);
  });
}

function resetVirtualScroll() {
  if (dom.tableWrap) {
    dom.tableWrap.scrollTop = 0;
  }
  state.renderStartIndex = 0;
  state.renderEndIndex = 50;
}

function syncMeasuredRowHeight() {
  const firstDataRow = dom.tableBody?.querySelector('tr[data-row-index]');
  if (!firstDataRow) return;
  const measuredHeight = firstDataRow.getBoundingClientRect().height;
  if (measuredHeight > 0) {
    state.rowHeight = measuredHeight;
  }
}

function initVirtualScroll(onViewportChange) {
  dom.tableWrap?.addEventListener('scroll', () => {
    const scrollTop = dom.tableWrap.scrollTop;
    const viewportHeight = dom.tableWrap.clientHeight;
    const overscan = 20;
    const newStart = Math.max(0, Math.floor(scrollTop / state.rowHeight) - overscan);
    const newEnd = Math.min(
      state.displayIndices.length,
      Math.ceil((scrollTop + viewportHeight) / state.rowHeight) + overscan
    );
    if (newStart === state.renderStartIndex && newEnd === state.renderEndIndex) return;
    state.renderStartIndex = newStart;
    state.renderEndIndex = newEnd;
    onViewportChange();
  });
}

function buildHeader(onSortClick) {
  dom.tableHead.innerHTML = '';
  const colDefs = getVisibleColDefs();

  if (!isMobile()) {
    const row = document.createElement('tr');
    let prevGroup = null;
    colDefs.forEach(col => {
      const th = document.createElement('th');
      const pipeIndex = col.fullName.indexOf('|');
      const metric = pipeIndex >= 0 ? col.fullName.slice(0, pipeIndex) : cleanColName(col.name);
      const date = pipeIndex >= 0 ? col.fullName.slice(pipeIndex + 1) : '';
      const unit = HEADER_UNIT_OVERRIDE[col.idx] ?? getColUnit(col);
      const unitHtml = unit ? `<span class="th-unit">${unit}</span>` : '';
      th.innerHTML = `<span class="th-metric">${metric}</span>${unitHtml}${date ? `<span class="th-date">${date}</span>` : ''}`;
      th.dataset.colidx = col.idx;
      th.dataset.group = col.group;
      if (col.group !== prevGroup) {
        th.classList.add('group-start');
        prevGroup = col.group;
      }
      if (String(state.sortCol) === String(col.idx)) {
        th.classList.add(state.sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      }
      if (isActiveColumn(col.idx)) th.classList.add('active-col');
      th.addEventListener('click', () => onSortClick(col.idx));
      row.appendChild(th);
    });
    dom.tableHead.appendChild(row);
  } else {
    const topRow = document.createElement('tr');
    const bottomRow = document.createElement('tr');
    let rankStartIndex = -1;
    let rankCount = 0;

    colDefs.forEach((col, index) => {
      const metric = cleanColName(col.name);
      if (metric.endsWith('排名') || metric === '综合分数') {
        if (rankStartIndex === -1) rankStartIndex = index;
        rankCount += 1;
      }
    });

    colDefs.forEach((col, index) => {
      const th = document.createElement('th');
      th.dataset.colidx = col.idx;
      if (String(state.sortCol) === String(col.idx)) {
        th.classList.add(state.sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      }
      if (isActiveColumn(col.idx)) th.classList.add('active-col');
      th.addEventListener('click', () => onSortClick(col.idx));

      const metric = cleanColName(col.name);
      const isRank = isRankMetricName(metric);

      if (isRank) {
        if (index === rankStartIndex) {
          const groupTh = document.createElement('th');
          groupTh.textContent = '排名维度';
          groupTh.colSpan = rankCount;
          groupTh.classList.add('rank-band');
          if (colDefs.some(current => isRankColumn(current) && isActiveColumn(current.idx))) {
            groupTh.classList.add('active-col');
          }
          topRow.appendChild(groupTh);
        }
        th.innerHTML = `<span class="th-metric">${metric.replace('排名', '')}</span>`;
        th.style.top = '22px';
        th.style.height = '24px';
        bottomRow.appendChild(th);
      } else {
        th.rowSpan = 2;
        const pipeIndex = col.fullName.indexOf('|');
        const headerMetric = pipeIndex >= 0 ? col.fullName.slice(0, pipeIndex) : metric;
        const date = pipeIndex >= 0 ? col.fullName.slice(pipeIndex + 1) : '';
        const unit = HEADER_UNIT_OVERRIDE[col.idx] ?? getColUnit(col);
        const unitHtml = unit ? `<span class="th-unit">${unit}</span>` : '';
        th.innerHTML = `<span class="th-metric">${headerMetric}</span>${unitHtml}${date ? `<span class="th-date">${date}</span>` : ''}`;
        topRow.appendChild(th);
      }
    });

    dom.tableHead.appendChild(topRow);
    dom.tableHead.appendChild(bottomRow);
  }

  if (isMobile()) {
    dom.mainTable.classList.toggle('table-has-code', getVisibleColDefs().some(col => col.idx === 1));
  }
}

function buildBody() {
  const colDefs = getVisibleColDefs();
  const totalRows = state.displayIndices.length;
  if (totalRows === 0) {
    dom.tableBody.innerHTML = '';
    return;
  }

  let html = '';
  const topSpacerHeight = state.renderStartIndex * state.rowHeight;
  const bottomSpacerHeight = (totalRows - state.renderEndIndex) * state.rowHeight;

  if (topSpacerHeight > 0) {
    html += `<tr style="height: ${topSpacerHeight}px; background: transparent;"><td colspan="${colDefs.length}" style="padding: 0; border: none;"></td></tr>`;
  }

  for (let index = state.renderStartIndex; index < state.renderEndIndex; index += 1) {
    if (index >= totalRows) break;
    const rowIndex = state.displayIndices[index];
    const row = DATA.rows[rowIndex];
    html += `<tr data-row-index="${index}">`;
    colDefs.forEach(col => {
      const rawValue = row[col.idx] ?? '--';
      const classes = [];
      if (isActiveColumn(col.idx)) classes.push('active-col');
      if (!col.locked) {
        const numericValue = parseStrictNum(String(rawValue));
        if (numericValue !== null) {
          if (isActiveColumn(col.idx) && isHighlightEligibleRankColumn(col)) classes.push('active-numeric');
          if (numericValue < 0) classes.push('neg');
          else if (numericValue > 0 && col.idx >= 4) classes.push('pos');
        }
      }
      const className = classes.length ? ` class="${classes.join(' ')}"` : '';
      html += `<td${className} data-colidx="${col.idx}">${fmtCell(rawValue, col)}</td>`;
    });
    html += '</tr>';
  }

  if (bottomSpacerHeight > 0) {
    html += `<tr style="height: ${bottomSpacerHeight}px; background: transparent;"><td colspan="${colDefs.length}" style="padding: 0; border: none;"></td></tr>`;
  }

  dom.tableBody.innerHTML = html;
  syncMeasuredRowHeight();
  revealTable();
}

let tableRevealed = false;
function revealTable() {
  if (tableRevealed) return;
  tableRevealed = true;
  const skeleton = document.getElementById('tableSkeleton');
  const table = document.getElementById('mainTable');
  if (skeleton) skeleton.remove();
  if (table) table.style.display = '';
}

function updateSummary() {
  dom.rowCount.textContent = state.displayIndices.length;
}

let xlsxLoaded = typeof XLSX !== 'undefined';
const XLSX_URL = 'https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js';

function loadXLSX() {
  if (xlsxLoaded) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = XLSX_URL;
    s.onload = () => { xlsxLoaded = true; resolve(); };
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

function exportExcel() {
  const btn = document.getElementById('exportBtn');
  const origText = btn.textContent;
  if (!xlsxLoaded) {
    btn.textContent = '加载中…';
    btn.disabled = true;
    loadXLSX().then(() => {
      btn.textContent = origText;
      btn.disabled = false;
      doExport();
    }).catch(() => {
      btn.textContent = origText;
      btn.disabled = false;
      alert('导出组件加载失败，请重试');
    });
    return;
  }
  doExport();
}

function doExport() {
  const colDefs = getVisibleColDefs();
  const headerRow = colDefs.map(col => {
    const pipeIndex = col.fullName.indexOf('|');
    const name = pipeIndex >= 0 ? col.fullName.slice(0, pipeIndex) : col.name;
    const date = pipeIndex >= 0 ? col.fullName.slice(pipeIndex + 1) : '';
    const unit = getColUnit(col);
    return name + (unit ? ` (${unit})` : '') + (date ? ` [${date}]` : '');
  });

  const dataRows = state.displayIndices.map((rowIndex, rowPos) => {
    const row = DATA.rows[rowIndex];
    return colDefs.map(col => {
      if (col.idx === 0) return rowPos + 1;
      const rawValue = row[col.idx] ?? '--';
      const display = fmtCell(rawValue, col);
      if (display === '--' || display === '') return '';
      const numericValue = parseFloat(display);
      return Number.isNaN(numericValue) ? display : numericValue;
    });
  });

  const workbook = XLSX.utils.book_new();
  const worksheet = XLSX.utils.aoa_to_sheet([headerRow, ...dataRows]);
  XLSX.utils.book_append_sheet(workbook, worksheet, '港股数据');
  XLSX.writeFile(workbook, '港股数据.xlsx');
}

function updateUpdateTime() {
  if (!window.STOCK_DATA?.update_time) return;
  if (dom.heroUpdateTime) {
    dom.heroUpdateTime.innerText = window.STOCK_DATA.update_time;
  }
}

window.DashboardView = {
  cleanColName,
  isRankMetricName,
  isActiveColumn,
  getVisibleColDefs,
  resetVirtualScroll,
  initVirtualScroll,
  buildHeader,
  buildBody,
  updateSummary,
  exportExcel,
  updateUpdateTime,
};
})();
