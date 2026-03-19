#!/usr/bin/env node
/**
 * validate.js - Node.js 验证工具，用于 compute.js 迭代时的统计与对比
 *
 * 用法:
 *   node validate.js                   # 输出当前计算结果统计
 *   node validate.js --snapshot a.json # 保存快照
 *   node validate.js --diff a.json     # 与快照对比差异
 *
 * 放在 indicators 分支，每次改完 compute.js 跑一次即可。
 */

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

// ── Parse CLI args ──
const args = process.argv.slice(2);
let snapshotPath = null;
let diffPath = null;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--snapshot' && args[i + 1]) snapshotPath = args[++i];
  else if (args[i] === '--diff' && args[i + 1]) diffPath = args[++i];
  else if (args[i] === '--help' || args[i] === '-h') {
    console.log(`用法:
  node validate.js                   显示计算结果统计
  node validate.js --snapshot a.json 保存快照到文件
  node validate.js --diff a.json     与快照对比差异
  node validate.js --snapshot b.json --diff a.json  保存新快照并与旧快照对比`);
    process.exit(0);
  }
}

// ── Load data.js + compute.js in sandboxed context ──
const rootDir = __dirname;
const dataJsPath = path.join(rootDir, 'data.js');
const computeJsPath = path.join(rootDir, 'assets', 'scripts', 'compute.js');

if (!fs.existsSync(dataJsPath)) {
  console.error('错误: 找不到 data.js，请先运行 python3 build_html.py');
  process.exit(1);
}
if (!fs.existsSync(computeJsPath)) {
  console.error('错误: 找不到 assets/scripts/compute.js');
  process.exit(1);
}

// Create a minimal browser-like environment
const sandbox = {
  window: {},
  console: console,
  performance: { now: () => {
    const [s, ns] = process.hrtime();
    return s * 1000 + ns / 1e6;
  }},
  Math: Math,
  String: String,
  Number: Number,
  Array: Array,
  Map: Map,
  Set: Set,
  parseFloat: parseFloat,
  parseInt: parseInt,
  isNaN: isNaN,
  isFinite: isFinite,
};
sandbox.globalThis = sandbox;

const ctx = vm.createContext(sandbox);

// Load data.js (sets window.STOCK_DATA)
const dataJs = fs.readFileSync(dataJsPath, 'utf-8');
vm.runInContext(dataJs, ctx, { filename: 'data.js' });

// Load compute.js (reads and mutates window.STOCK_DATA.rows)
const computeJs = fs.readFileSync(computeJsPath, 'utf-8');
vm.runInContext(computeJs, ctx, { filename: 'compute.js' });

const STOCK_DATA = sandbox.window.STOCK_DATA;
const rows = STOCK_DATA.rows;
const CM = STOCK_DATA.computed_col_map;
const totalStocks = rows.length;

// ── Collect stats ──
function collectStats() {
  const stats = {};

  // For each computed column, count non-null values
  for (const [name, idx] of Object.entries(CM)) {
    let nonNull = 0;
    let values = [];
    for (let i = 0; i < totalStocks; i++) {
      const v = rows[i][idx];
      if (v !== null && v !== undefined && v !== '--') {
        nonNull++;
        const num = parseFloat(String(v).replace(/,/g, ''));
        if (!isNaN(num)) values.push(num);
      }
    }
    const s = { nonNull, total: totalStocks };
    if (values.length > 0) {
      values.sort((a, b) => a - b);
      s.min = values[0];
      s.max = values[values.length - 1];
      s.median = values[Math.floor(values.length / 2)];
      s.mean = Math.round(values.reduce((a, b) => a + b, 0) / values.length * 100) / 100;
    }
    stats[name] = s;
  }

  // Financial / non-financial split
  const JINRONG_SET = new Set(['保险', '其他金融', '银行']);
  let jinrongCount = 0;
  for (let i = 0; i < totalStocks; i++) {
    const ind = String(rows[i][9] || '');
    if (JINRONG_SET.has(ind)) jinrongCount++;
  }
  stats._meta = {
    totalStocks,
    financial: jinrongCount,
    nonFinancial: totalStocks - jinrongCount,
  };

  return stats;
}

const stats = collectStats();

// ── Display stats ──
function displayStats(stats) {
  const meta = stats._meta;
  console.log(`\n总股票数: ${meta.totalStocks}  (金融: ${meta.financial}, 非金融: ${meta.nonFinancial})\n`);
  console.log('指标                     非空数   占比     最小值       中位数       最大值');
  console.log('─'.repeat(80));

  for (const [name, idx] of Object.entries(CM)) {
    const s = stats[name];
    const pct = (s.nonNull / s.total * 100).toFixed(1).padStart(5);
    const nn = String(s.nonNull).padStart(4);
    const label = name.padEnd(20);

    if (s.min !== undefined) {
      const fmt = v => {
        if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(1) + '亿';
        if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(1) + '万';
        return v.toFixed(2);
      };
      console.log(`  ${label} ${nn}/${s.total}  ${pct}%    ${fmt(s.min).padStart(12)}  ${fmt(s.median).padStart(12)}  ${fmt(s.max).padStart(12)}`);
    } else {
      console.log(`  ${label} ${nn}/${s.total}  ${pct}%`);
    }
  }
  console.log();
}

displayStats(stats);

// ── Save snapshot ──
if (snapshotPath) {
  // Save per-stock detail for diff
  const detail = {};
  for (const [name, idx] of Object.entries(CM)) {
    detail[name] = rows.map(r => r[idx]);
  }
  const snapshot = { stats, detail, timestamp: new Date().toISOString() };
  fs.writeFileSync(snapshotPath, JSON.stringify(snapshot, null, 2), 'utf-8');
  console.log(`快照已保存: ${snapshotPath}`);
}

// ── Diff with previous snapshot ──
if (diffPath) {
  if (!fs.existsSync(diffPath)) {
    console.error(`对比文件不存在: ${diffPath}`);
    process.exit(1);
  }
  const old = JSON.parse(fs.readFileSync(diffPath, 'utf-8'));
  const oldStats = old.stats;
  const oldDetail = old.detail;

  console.log(`\n══ 对比: 当前 vs ${diffPath} (${old.timestamp}) ══\n`);
  console.log('指标                     旧非空  →  新非空   变化');
  console.log('─'.repeat(60));

  let totalChanged = 0;
  for (const [name, idx] of Object.entries(CM)) {
    const oldS = oldStats[name];
    const newS = stats[name];
    if (!oldS) continue;
    const diff = newS.nonNull - oldS.nonNull;
    const arrow = diff > 0 ? `+${diff}` : diff < 0 ? `${diff}` : ' 0';
    const label = name.padEnd(20);
    const changed = diff !== 0;
    if (changed) totalChanged++;
    const mark = changed ? ' ◀' : '';
    console.log(`  ${label} ${String(oldS.nonNull).padStart(4)}  →  ${String(newS.nonNull).padStart(4)}   ${arrow.padStart(4)}${mark}`);
  }

  // Ranking columns: derived from computed metrics, changes are expected cascade
  // Report them separately so they don't clutter the core metrics diff
  const RANKING_COLS = new Set(['低估排名', '成长排名', '质量排名', '股东回报排名', '综合分数', '综合排名']);

  // Per-stock value changes
  if (oldDetail) {
    console.log(`\n── 计算指标变化明细（排除排名列）──\n`);
    let metricChangeCount = 0;
    let rankingChangeCount = 0;
    for (const [name, idx] of Object.entries(CM)) {
      const oldVals = oldDetail[name];
      if (!oldVals) continue;
      const newVals = rows.map(r => r[idx]);
      const isRanking = RANKING_COLS.has(name);
      const changes = [];
      let nullToValue = 0, valueToNull = 0, valueToValue = 0;
      for (let i = 0; i < Math.min(oldVals.length, newVals.length); i++) {
        const ov = oldVals[i];
        const nv = newVals[i];
        if (String(ov) !== String(nv)) {
          const wasNull = (ov === null || ov === undefined || ov === '--');
          const isNull = (nv === null || nv === undefined || nv === '--');
          if (wasNull && !isNull) nullToValue++;
          else if (!wasNull && isNull) valueToNull++;
          else valueToValue++;
          changes.push({ stock: `${rows[i][1]} ${rows[i][2]}`, old: ov, new: nv });
        }
      }
      if (changes.length > 0) {
        if (isRanking) {
          rankingChangeCount += changes.length;
        } else {
          metricChangeCount += changes.length;
          const parts = [];
          if (nullToValue > 0) parts.push(`空→有值 ${nullToValue}`);
          if (valueToNull > 0) parts.push(`有值→空 ${valueToNull}`);
          if (valueToValue > 0) parts.push(`值变化 ${valueToValue}`);
          console.log(`  ${name}: ${changes.length} 条变化  (${parts.join(', ')})`);
          // Show first 5 examples
          for (const c of changes.slice(0, 5)) {
            console.log(`    ${c.stock}: ${c.old} → ${c.new}`);
          }
          if (changes.length > 5) console.log(`    ... 及其他 ${changes.length - 5} 条`);
        }
      }
    }
    if (metricChangeCount === 0) console.log('  计算指标无变化');
    else console.log(`\n计算指标总变化: ${metricChangeCount} 个单元格`);
    if (rankingChangeCount > 0) {
      console.log(`排名列传导变化: ${rankingChangeCount} 个单元格（明细已省略）`);
    }
  }

  console.log();
}
