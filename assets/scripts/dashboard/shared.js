(() => {
const dataSource = window.STOCK_DATA;
const dom = window.DashboardDOM;

const DATA = { headers: dataSource.headers, rows: dataSource.rows };
const COLS = dataSource.cols;
const PERIODS = dataSource.periods;
const METRICS = dataSource.metrics;
const ROIC_START = dataSource.roic_start;
const ROIC_END = dataSource.roic_end;
const TTMROE_IDX = dataSource.ttmroe_idx;
const TTMROIC_IDX = dataSource.ttmroic_idx;
const PCT_METRICS = new Set(['净利润同比', 'ROE', 'ROIC']);
const COMPUTED_YI_COLS = new Set(dataSource.computed_yi_cols);
const COMPUTED_COL_NAMES = dataSource.computed_col_names;
const FILTER_COLS = dataSource.filter_cols;
const METRICS_DEFAULT_HIDDEN = new Set(dataSource.metrics_hidden);
const COMPUTED_DEFAULT_HIDDEN = new Set(dataSource.computed_hidden);
const FIXED_DEFAULT_HIDDEN = new Set(dataSource.fixed_hidden || []);

if (dom.totalCount) {
  dom.totalCount.textContent = dataSource.row_count;
}

function isMobile() {
  return window.innerWidth < 768;
}

function parseNum(value) {
  if (value === null || value === undefined || value === '--') return null;
  let normalized = String(value).replace(/,/g, '');
  let multiplier = 1;
  if (normalized.endsWith('亿')) {
    multiplier = 1e8;
    normalized = normalized.slice(0, -1);
  } else if (normalized.endsWith('万')) {
    multiplier = 1e4;
    normalized = normalized.slice(0, -1);
  }
  const parsed = parseFloat(normalized);
  return Number.isNaN(parsed) ? null : parsed * multiplier;
}

function parseStrictNum(value) {
  if (value === null || value === undefined || value === '--') return null;
  let normalized = String(value).replace(/,/g, '').trim();
  let multiplier = 1;
  if (normalized.endsWith('亿')) {
    multiplier = 1e8;
    normalized = normalized.slice(0, -1);
  } else if (normalized.endsWith('万')) {
    multiplier = 1e4;
    normalized = normalized.slice(0, -1);
  }
  if (!/^[+-]?(?:\d+\.?\d*|\.\d+)$/.test(normalized)) return null;
  const parsed = parseFloat(normalized);
  return Number.isNaN(parsed) ? null : parsed * multiplier;
}

function fmtYi(value) {
  const yi = value / 1e8;
  return Math.abs(yi) >= 1 ? yi.toFixed(1) : yi.toFixed(2);
}

function getColUnit(col) {
  if (col.idx === 5) return '亿';
  if (col.idx === 8) return '亿股';
  if (COMPUTED_YI_COLS.has(col.idx)) return '亿';
  if (
    col.idx === 12 ||
    col.idx === TTMROE_IDX ||
    col.idx === TTMROIC_IDX ||
    col.idx === 32 ||
    col.idx === 33
  ) return '%';
  if (col.group !== '基本信息' && col.group !== '计算指标' && !PCT_METRICS.has(col.group)) return '亿';
  return '';
}

function fmtCell(value, col) {
  if (value === '--' || value === null || value === undefined) return '--';
  if (col.idx === 6 || col.idx === 7) {
    const parsed = parseNum(String(value));
    return parsed === null ? value : parsed.toFixed(1);
  }
  if (col.idx === 10) return value;
  if (
    col.idx === 12 ||
    col.idx === TTMROE_IDX ||
    col.idx === TTMROIC_IDX ||
    col.idx === 32 ||
    col.idx === 33
  ) {
    const parsed = parseNum(String(value));
    return parsed === null ? value : parsed.toFixed(1);
  }
  if (!getColUnit(col)) return value;
  const parsed = parseNum(String(value));
  if (parsed === null) return value;
  return fmtYi(parsed);
}

function isJinRong(row) {
  const industry = String(row[9]);
  if (industry === '保险' || industry === '其他金融' || industry === '银行') return true;
  if (industry === '综合企业' && String(row[2]).includes('中信股份')) return true;
  return false;
}

function getStockType(row) {
  return isJinRong(row) ? '金融股' : '非金融股';
}

window.DashboardShared = {
  DATA,
  COLS,
  PERIODS,
  METRICS,
  ROIC_START,
  ROIC_END,
  TTMROE_IDX,
  TTMROIC_IDX,
  PCT_METRICS,
  COMPUTED_YI_COLS,
  COMPUTED_COL_NAMES,
  FILTER_COLS,
  METRICS_DEFAULT_HIDDEN,
  COMPUTED_DEFAULT_HIDDEN,
  FIXED_DEFAULT_HIDDEN,
  isMobile,
  parseNum,
  parseStrictNum,
  fmtYi,
  getColUnit,
  fmtCell,
  isJinRong,
  getStockType,
};
})();
