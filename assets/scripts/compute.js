/**
 * compute.js - Client-side computation engine for HK Stocks Dashboard
 *
 * Reads raw period data from STOCK_DATA.rows (idx 40+) and computes:
 *   Phase 1: per-stock derived metrics (idx 10-33)
 *   Phase 2: cross-stock rankings (idx 34-39)
 *
 * Runs once at page load before dashboard initialization.
 * Produces the same flat array values as the former Python pipeline.
 */
(() => {
'use strict';

const D = window.STOCK_DATA;
const rows = D.rows;
const cols = D.cols;
const CM = D.computed_col_map;
const PERIODS = D.periods;
const JINRONG_SET = new Set(['保险', '其他金融', '银行']);

// ── Build period lookup: periodIdx[displayMetric][periodLabel] = column index ──
const periodIdx = {};
cols.forEach(col => {
  const pipe = col.fullName.indexOf('|');
  if (pipe < 0) return;
  const metric = col.fullName.slice(0, pipe);
  const period = col.fullName.slice(pipe + 1);
  if (!periodIdx[metric]) periodIdx[metric] = {};
  periodIdx[metric][period] = col.idx;
});

// ── Utility functions ──

/** Parse a cell value to float (handles 亿/万 suffixes, commas, '--') */
function parseN(val) {
  if (val === null || val === undefined || val === '--' || val === '') return null;
  let s = String(val).replace(/,/g, '');
  let mul = 1;
  if (s.endsWith('亿')) { mul = 1e8; s = s.slice(0, -1); }
  else if (s.endsWith('万')) { mul = 1e4; s = s.slice(0, -1); }
  const f = parseFloat(s);
  return isNaN(f) ? null : f * mul;
}

/** Get float value from a period data cell */
function gf(row, metric, period) {
  const idx = periodIdx[metric] && periodIdx[metric][period];
  if (idx === undefined) return null;
  return parseN(row[idx]);
}

/** Format value to match Python format_value output */
function fmtV(v) {
  if (v === null || v === undefined) return '--';
  if (typeof v === 'number') {
    if (!isFinite(v)) return '--';
    if (v === Math.floor(v) && Math.abs(v) < 1e13) return String(v);
    return String(Math.round(v * 10000) / 10000);
  }
  return String(v);
}

/** Check if stock is financial sector (mutates industry for 中信股份) */
function isJinRong(row) {
  const ind = String(row[9] || '');
  const name = String(row[2] || '');
  if (ind === '综合企业' && name.includes('中信股份')) {
    row[9] = '其他金融';
    return true;
  }
  return JINRONG_SET.has(ind);
}

// ── Phase 1: Per-stock computation ──

function computePhase1(row) {
  const g = (metric, period) => gf(row, metric, period);

  // Determine latest reporting period
  const hasAnnual = g('归母净利润', '2025年报') !== null;
  const hasQ3 = g('归母净利润', '2025三季报') !== null;
  const latestPeriod = hasAnnual ? '2025年报' : (hasQ3 ? '2025三季报' : '2025中报');

  // Standard TTM: recent_quarter + prior_annual - prior_same_quarter
  function ttm(metric, qLatest, annual, qBase) {
    const recent = g(metric, qLatest);
    const annualFull = g(metric, annual);
    const base = g(metric, qBase);
    if (recent === null || annualFull === null || base === null) return null;
    return recent + (annualFull - base);
  }

  // ── TTM profit & YoY ──
  let ttmProfit, ttmYoy;
  if (hasAnnual) {
    ttmProfit = g('归母净利润', '2025年报');
    const ttmBase = g('归母净利润', '2024年报');
    const annualYoy = g('净利润同比', '2025年报');
    if (annualYoy !== null) {
      ttmYoy = annualYoy;
    } else if (ttmProfit !== null && ttmBase && ttmBase !== 0) {
      ttmYoy = (ttmProfit - ttmBase) / Math.abs(ttmBase) * 100;
    } else {
      ttmYoy = null;
    }
  } else if (hasQ3) {
    ttmProfit = ttm('归母净利润', '2025三季报', '2024年报', '2024三季报');
    const ttmBase = ttm('归母净利润', '2024三季报', '2023年报', '2023三季报');
    ttmYoy = (ttmProfit !== null && ttmBase && ttmBase !== 0)
      ? (ttmProfit - ttmBase) / Math.abs(ttmBase) * 100 : null;
  } else {
    ttmProfit = ttm('归母净利润', '2025中报', '2024年报', '2024中报');
    const ttmBase = ttm('归母净利润', '2024中报', '2023年报', '2023中报');
    ttmYoy = (ttmProfit !== null && ttmBase && ttmBase !== 0)
      ? (ttmProfit - ttmBase) / Math.abs(ttmBase) * 100 : null;
  }

  // ── TTM for percentage metrics (ROE, ROIC) ──
  function ttmPct(metric) {
    if (hasAnnual) {
      const annual = g(metric, '2025年报');
      if (annual !== null) return annual;
    }
    const q3 = g(metric, '2025三季报');
    if (q3 !== null) {
      const annual = g(metric, '2024年报');
      const base = g(metric, '2024三季报');
      return (annual !== null && base !== null) ? (q3 + (annual - base)) : (q3 / 3 * 4);
    }
    const h1 = g(metric, '2025中报');
    if (h1 !== null) {
      const annual = g(metric, '2024年报');
      const base = g(metric, '2024中报');
      return (annual !== null && base !== null) ? (h1 + (annual - base)) : (h1 * 2);
    }
    return null;
  }

  // ── TTM for cash flow metrics (absolute values) ──
  function ttmYi(metric) {
    if (hasAnnual) {
      const annual = g(metric, '2025年报');
      if (annual !== null) return annual;
    }
    const q3 = g(metric, '2025三季报');
    if (q3 !== null) return ttm(metric, '2025三季报', '2024年报', '2024三季报');
    const h1 = g(metric, '2025中报');
    if (h1 !== null) return ttm(metric, '2025中报', '2024年报', '2024中报');
    return null;
  }

  function negOnly(v) { return (v === null || v > 0) ? null : v; }
  function negateNegOnly(v) {
    if (v === null) return null;
    return (-v > 0) ? null : -v;
  }
  function gv(metric) { return g(metric, latestPeriod); }

  // ── Core computations ──
  const financial = isJinRong(row);
  const ttmRoe = ttmPct('ROE');
  const ttmRoic = ttmPct('ROIC');
  const ttmOcf = ttmYi('经营现金流');
  const ttmIcf = ttmYi('投资现金流');
  const ttmCapex = negateNegOnly(ttmYi('资本支出'));

  let netCash, interestDebt, ttmFcf, shareholderYield;
  if (financial) {
    netCash = null;
    interestDebt = null;
    ttmFcf = null;
    shareholderYield = null;
  } else {
    const cash = gv('总现金'), stDebt = gv('短期借款'), ltDebt = gv('长期借款');
    if (cash === null && stDebt === null && ltDebt === null) {
      netCash = null;
      interestDebt = null;
    } else {
      netCash = (cash || 0) - (stDebt || 0) - (ltDebt || 0);
      interestDebt = (stDebt || 0) + (ltDebt || 0);
    }
    const fcf1 = (ttmOcf !== null && ttmCapex !== null) ? ttmOcf + ttmCapex : null;
    const fcf2 = (ttmOcf !== null && ttmIcf !== null) ? ttmOcf + ttmIcf : null;
    ttmFcf = fcf1 !== null ? fcf1 : fcf2;

    const mktCap = parseN(row[5]);
    if (ttmFcf !== null && mktCap !== null && netCash !== null) {
      const denom = mktCap - netCash;
      shareholderYield = denom !== 0 ? (ttmFcf / denom * 100) : null;
    } else {
      shareholderYield = null;
    }
  }

  // ── Expected dividend ──
  const actualDiv2025 = g('年度分红', '2025年报');
  let expectedDiv;
  if (hasAnnual) {
    expectedDiv = actualDiv2025 === null ? null : Math.max(actualDiv2025, 0);
  } else {
    const div2024 = g('年度分红', '2024年报');
    const projected = (div2024 === null || ttmYoy === null) ? null : div2024 * (1 + ttmYoy / 100);
    expectedDiv = projected === null ? null : Math.max(projected, 0);
  }

  // ── Expected shareholder return ──
  const buybackRaw = negOnly(ttmYi('股份回购'));
  const buybackAbs = buybackRaw !== null ? -buybackRaw : 0;
  const expectedReturn = (expectedDiv || 0) + (buybackAbs / 2);
  let returnRatio = (ttmProfit === null || ttmProfit === 0)
    ? null : expectedReturn / ttmProfit * 100;
  if (returnRatio !== null && returnRatio < 0) returnRatio = 0;

  // ── PE for ranking ──
  const peTtm = parseN(row[6]);

  // ── Net assets (search across periods) ──
  let netAssets = null;
  for (let p = 0; p < PERIODS.length; p++) {
    netAssets = gf(row, '权益合计', PERIODS[p]);
    if (netAssets !== null) break;
  }

  // ── Write computed values into row[10..33] ──
  row[CM['最新财报季']] = latestPeriod;
  row[CM['TTM归母净利润']] = fmtV(ttmProfit);
  row[CM['TTM净利同比']] = fmtV(ttmYoy);
  row[CM['最新总现金']] = fmtV(gv('总现金'));
  row[CM['最新流动资产']] = fmtV(gv('流动资产'));
  row[CM['最新总负债']] = fmtV(gv('总负债'));
  row[CM['最新短期借款']] = fmtV(gv('短期借款'));
  row[CM['最新长期借款']] = fmtV(gv('长期借款'));
  row[CM['最新权益合计']] = fmtV(netAssets);
  row[CM['TTMROE']] = fmtV(ttmRoe);
  row[CM['TTMROIC']] = fmtV(ttmRoic);
  row[CM['TTM经营现金流']] = fmtV(ttmOcf);
  row[CM['TTM投资现金流']] = fmtV(ttmIcf);
  row[CM['TTM资本支出']] = fmtV(ttmCapex);
  row[CM['TTM融资现金流']] = fmtV(ttmYi('融资现金流'));
  row[CM['TTM股份回购']] = fmtV(negOnly(ttmYi('股份回购')));
  row[CM['TTM支付股息']] = fmtV(negOnly(ttmYi('支付股息')));
  row[CM['预期25年度分红']] = fmtV(expectedDiv);
  row[CM['预期25股东回报']] = fmtV(expectedReturn);
  row[CM['净现金']] = fmtV(netCash);
  row[CM['有息负债']] = fmtV(interestDebt);
  row[CM['TTMFCF']] = fmtV(ttmFcf);
  row[CM['股东收益率']] = fmtV(shareholderYield);
  row[CM['股东回报分配率']] = fmtV(returnRatio);

  return {
    isJinrong: financial,
    ttmYoy: ttmYoy,
    ttmroe: ttmRoe,
    ttmroic: ttmRoic,
    peTtm: peTtm,
    shareholderYield: shareholderYield,
    returnRatio: returnRatio,
  };
}

// ── Phase 2: Cross-row rankings ──

function competitionRank(sortedItems) {
  const ranks = new Map();
  for (let pos = 0; pos < sortedItems.length; pos++) {
    const [idx, value] = sortedItems[pos];
    if (pos === 0) {
      ranks.set(idx, 1);
    } else if (value === sortedItems[pos - 1][1]) {
      ranks.set(idx, ranks.get(sortedItems[pos - 1][0]));
    } else {
      ranks.set(idx, pos + 1);
    }
  }
  return ranks;
}

function computeRankings(phase1List) {
  const count = phase1List.length;
  const financial = [];
  const nonFinancial = [];
  for (let i = 0; i < count; i++) {
    if (phase1List[i].isJinrong) financial.push(i);
    else nonFinancial.push(i);
  }

  const rkStr = v => v === null ? '--' : String(v);
  const compStr = v => v === null ? '--' : (Number.isInteger(v) ? v.toFixed(1) : String(v));
  let ranks;

  // ── Undervalue ──
  const undervalue = new Array(count).fill(null);
  // Financial: by PE ascending (PE <= 0 excluded)
  const finPE = financial
    .filter(i => phase1List[i].peTtm !== null && phase1List[i].peTtm > 0)
    .map(i => [i, phase1List[i].peTtm]);
  finPE.sort((a, b) => a[1] - b[1]);
  ranks = competitionRank(finPE);
  for (const idx of financial) {
    const pe = phase1List[idx].peTtm;
    if (pe !== null && pe > 0) undervalue[idx] = ranks.get(idx);
  }
  // Non-financial: by shareholder yield descending (<=0 excluded)
  const nfYield = nonFinancial
    .filter(i => phase1List[i].shareholderYield !== null && phase1List[i].shareholderYield > 0)
    .map(i => [i, phase1List[i].shareholderYield]);
  nfYield.sort((a, b) => b[1] - a[1]);
  ranks = competitionRank(nfYield);
  for (const idx of nonFinancial) {
    const sy = phase1List[idx].shareholderYield;
    if (sy !== null && sy > 0) undervalue[idx] = ranks.get(idx);
  }

  // ── Growth (null does not participate) ──
  const growth = new Array(count).fill(null);
  for (const queue of [financial, nonFinancial]) {
    const items = queue
      .filter(i => phase1List[i].ttmYoy !== null)
      .map(i => [i, phase1List[i].ttmYoy]);
    items.sort((a, b) => b[1] - a[1]);
    ranks = competitionRank(items);
    for (const idx of queue) {
      if (phase1List[idx].ttmYoy !== null) growth[idx] = ranks.get(idx);
    }
  }

  // ── Quality ──
  const quality = new Array(count).fill(null);
  // Financial: by ROE descending
  const finQ = financial
    .filter(i => phase1List[i].ttmroe !== null)
    .map(i => [i, phase1List[i].ttmroe]);
  finQ.sort((a, b) => b[1] - a[1]);
  ranks = competitionRank(finQ);
  for (const idx of financial) {
    if (phase1List[idx].ttmroe !== null) quality[idx] = ranks.get(idx);
  }
  // Non-financial: by ROIC descending
  const nfQ = nonFinancial
    .filter(i => phase1List[i].ttmroic !== null)
    .map(i => [i, phase1List[i].ttmroic]);
  nfQ.sort((a, b) => b[1] - a[1]);
  ranks = competitionRank(nfQ);
  for (const idx of nonFinancial) {
    if (phase1List[idx].ttmroic !== null) quality[idx] = ranks.get(idx);
  }

  // ── Return distribution ──
  const returnDist = new Array(count).fill(null);
  for (const queue of [financial, nonFinancial]) {
    const queueSize = queue.length;
    const positive = queue
      .filter(i => phase1List[i].returnRatio !== null && phase1List[i].returnRatio > 0)
      .map(i => [i, phase1List[i].returnRatio]);
    positive.sort((a, b) => b[1] - a[1]);
    ranks = competitionRank(positive);
    for (const idx of queue) {
      const rr = phase1List[idx].returnRatio;
      returnDist[idx] = (rr !== null && rr > 0) ? (ranks.get(idx) || queueSize) : queueSize;
    }
  }

  // ── Composite score ──
  const composite = new Array(count).fill(null);
  for (let i = 0; i < count; i++) {
    if (undervalue[i] !== null && growth[i] !== null &&
        quality[i] !== null && returnDist[i] !== null) {
      composite[i] = Math.round(
        (undervalue[i] * 0.4 + growth[i] * 0.2 + quality[i] * 0.2 + returnDist[i] * 0.2) * 10
      ) / 10;
    }
  }

  // ── Composite rank ──
  const compositeRank = new Array(count).fill(null);
  for (const queue of [financial, nonFinancial]) {
    const items = queue
      .filter(i => composite[i] !== null)
      .map(i => [i, composite[i]]);
    items.sort((a, b) => a[1] - b[1]);
    ranks = competitionRank(items);
    for (const idx of queue) {
      if (composite[idx] !== null) compositeRank[idx] = ranks.get(idx);
    }
  }

  // ── Write rankings into rows[34..39] ──
  for (let i = 0; i < count; i++) {
    rows[i][CM['低估排名']] = rkStr(undervalue[i]);
    rows[i][CM['成长排名']] = rkStr(growth[i]);
    rows[i][CM['质量排名']] = rkStr(quality[i]);
    rows[i][CM['股东回报排名']] = rkStr(returnDist[i]);
    rows[i][CM['综合分数']] = compStr(composite[i]);
    rows[i][CM['综合排名']] = rkStr(compositeRank[i]);
  }
}

// ── Execute ──
const t0 = performance.now();
const phase1Results = rows.map(row => computePhase1(row));
computeRankings(phase1Results);
const t1 = performance.now();
console.log('[compute.js] ' + rows.length + ' stocks computed in ' + (t1 - t0).toFixed(1) + 'ms');
})();
