import { dom } from './dom.js';
import { COLS, PERIODS, METRICS, COMPUTED_COL_NAMES, isMobile } from './shared.js';
import { FIXED_TOGGLEABLE_NAMES, state } from './state.js';

const COMPUTED_GROUPS = [
  { label: '盈利', cols: ['TTM归母净利润', 'TTM净利同比'] },
  { label: '回报率', cols: ['TTMROE', 'TTMROIC', '股东收益率', '股东回报分配率'] },
  { label: '现金流', cols: ['TTM经营现金流', 'TTM投资现金流', 'TTM资本支出', 'TTM融资现金流', 'TTMFCF'] },
  { label: '资产负债', cols: ['最新总现金', '最新流动资产', '最新总负债', '最新短期借款', '最新长期借款', '最新权益合计', '净现金', '有息负债'] },
  { label: '分红回购', cols: ['TTM股份回购', 'TTM支付股息', '预期25年度分红', '预期25股东回报'] },
  { label: '排名', cols: ['低估排名', '成长排名', '质量排名', '股东回报排名', '综合分数', '综合排名'] },
];

function makeSection(title, items, activeSet) {
  let html = `<div class="cp-group">
    <div class="cp-group-hdr">
      <span class="cp-group-name">${title}</span>
      <button class="cp-group-btn" data-sec="${title}" data-a="all">全选</button>
      <button class="cp-group-btn" data-sec="${title}" data-a="none">全不选</button>
    </div><div class="cp-cols">`;
  items.forEach(item => {
    const checked = activeSet.has(item) ? 'checked' : '';
    html += `<label class="cp-col"><input type="checkbox" data-sec="${title}" data-val="${item}" ${checked}> ${item}</label>`;
  });
  html += '</div></div>';
  return html;
}

function makeComputedSection() {
  let html = `<div class="cp-group"><div class="cp-group-hdr">
    <span class="cp-group-name">计算指标</span>
    <button class="cp-group-btn" data-sec="computed" data-a="all">全选</button>
    <button class="cp-group-btn" data-sec="computed" data-a="none">全不选</button>
    </div><div class="cp-cols">`;
  COMPUTED_GROUPS.forEach(group => {
    html += `<span class="cp-sublabel">${group.label}</span>`;
    group.cols.forEach(name => {
      html += `<label class="cp-col"><input type="checkbox" data-sec="computed" data-val="${name}" ${state.visibleComputedCols.has(name) ? 'checked' : ''}> ${name}</label>`;
    });
  });
  return `${html}</div></div>`;
}

function makeFixedSection() {
  const codeColName = isMobile() ? COLS.find(col => col.idx === 1)?.name : null;
  if (!FIXED_TOGGLEABLE_NAMES.length && !codeColName) return '';

  let html = `<div class="cp-group"><div class="cp-group-hdr">
    <span class="cp-group-name">基本信息</span>
    <button class="cp-group-btn" data-sec="fixed" data-a="all">全选</button>
    <button class="cp-group-btn" data-sec="fixed" data-a="none">全不选</button>
    </div><div class="cp-cols">`;
  if (codeColName) {
    html += `<label class="cp-col"><input type="checkbox" data-sec="fixed" data-val="${codeColName}" ${state.visibleFixedCols.has(codeColName) ? 'checked' : ''}> ${codeColName}</label>`;
  }
  FIXED_TOGGLEABLE_NAMES.forEach(name => {
    html += `<label class="cp-col"><input type="checkbox" data-sec="fixed" data-val="${name}" ${state.visibleFixedCols.has(name) ? 'checked' : ''}> ${name}</label>`;
  });
  html += `<label class="cp-col"><input type="checkbox" data-sec="computed" data-val="最新财报季" ${state.visibleComputedCols.has('最新财报季') ? 'checked' : ''}> 最新财报季</label>`;
  return `${html}</div></div>`;
}

function getSectionBinding(section) {
  if (section === 'fixed') {
    const mobileCodeCol = isMobile() ? COLS.find(col => col.idx === 1)?.name : null;
    const items = mobileCodeCol ? [mobileCodeCol, ...FIXED_TOGGLEABLE_NAMES] : FIXED_TOGGLEABLE_NAMES;
    return { activeSet: state.visibleFixedCols, items };
  }
  if (section === 'computed') return { activeSet: state.visibleComputedCols, items: COMPUTED_COL_NAMES };
  if (section === '财报周期') return { activeSet: state.visiblePeriods, items: PERIODS };
  return { activeSet: state.visibleMetrics, items: METRICS };
}

export function buildColPicker(onVisibilityChange) {
  dom.cpBody.innerHTML =
    makeFixedSection() +
    makeComputedSection() +
    makeSection('财报周期', PERIODS, state.visiblePeriods) +
    makeSection('财务指标', METRICS, state.visibleMetrics);

  dom.cpBody.querySelectorAll('input[data-sec]').forEach(checkbox => {
    checkbox.addEventListener('change', event => {
      const { activeSet } = getSectionBinding(event.target.dataset.sec);
      if (event.target.checked) activeSet.add(event.target.dataset.val);
      else activeSet.delete(event.target.dataset.val);
      onVisibilityChange();
    });
  });

  dom.cpBody.querySelectorAll('.cp-group-btn').forEach(button => {
    button.addEventListener('click', event => {
      const { activeSet, items } = getSectionBinding(event.target.dataset.sec);
      if (event.target.dataset.a === 'all') {
        items.forEach(item => activeSet.add(item));
      } else {
        activeSet.clear();
      }
      buildColPicker(onVisibilityChange);
      onVisibilityChange();
    });
  });
}

export function openColPicker(onVisibilityChange) {
  dom.colPicker.classList.add('open');
  dom.cpOverlay.classList.add('open');
  dom.colPickerBtn.classList.add('active');
  buildColPicker(onVisibilityChange);
}

export function closeColPicker() {
  dom.colPicker.classList.remove('open');
  dom.cpOverlay.classList.remove('open');
  dom.colPickerBtn.classList.remove('active');
}

export function initColumnPicker(onVisibilityChange) {
  dom.colPickerBtn.addEventListener('click', () => {
    if (dom.colPicker.classList.contains('open')) {
      closeColPicker();
    } else {
      openColPicker(onVisibilityChange);
    }
  });
  dom.cpClose.addEventListener('click', closeColPicker);
  dom.cpOverlay.addEventListener('click', closeColPicker);
}
