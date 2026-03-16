(() => {
const dom = window.DashboardDOM;
const { DATA, FILTER_COLS, getStockType, parseNum } = window.DashboardShared;
const { state } = window.DashboardState;

function updateIndustryFilter() {
  dom.industryFilter.innerHTML = '<option value="">所有行业</option>';
  const industries = new Set();
  DATA.rows.forEach(row => {
    if (getStockType(row) === state.filterStockType && row[9]) {
      industries.add(row[9]);
    }
  });
  Array.from(industries).sort().forEach(industry => {
    const option = document.createElement('option');
    option.value = industry;
    option.textContent = industry;
    dom.industryFilter.appendChild(option);
  });
  if (industries.has(state.filterIndustry)) {
    dom.industryFilter.value = state.filterIndustry;
  } else {
    state.filterIndustry = '';
    dom.industryFilter.value = '';
  }
}

function applyFilters() {
  let indices = DATA.rows.map((_, index) => index);
  if (state.filterStockType) {
    indices = indices.filter(index => getStockType(DATA.rows[index]) === state.filterStockType);
  }
  dom.totalCount.textContent = indices.length;

  if (state.filterIndustry) {
    indices = indices.filter(index => DATA.rows[index][9] === state.filterIndustry);
  }
  if (state.searchText) {
    const keyword = state.searchText.toLowerCase();
    indices = indices.filter(index =>
      String(DATA.rows[index][1]).toLowerCase().includes(keyword) ||
      String(DATA.rows[index][2]).toLowerCase().includes(keyword)
    );
  }
  Object.entries(state.filters).forEach(([idx, filter]) => {
    const colIndex = parseInt(idx, 10);
    const filterCol = FILTER_COLS.find(col => col.idx === colIndex);
    const threshold = filterCol?.isYi && filter.val !== null ? filter.val * 1e8 : filter.val;
    indices = indices.filter(index => {
      const numericValue = parseNum(String(DATA.rows[index][colIndex]));
      if (filter.op === 'empty') return numericValue === null;
      if (numericValue === null) return false;
      if (filter.op === '>') return numericValue > threshold;
      if (filter.op === '>=') return numericValue >= threshold;
      if (filter.op === '<') return numericValue < threshold;
      if (filter.op === '<=') return numericValue <= threshold;
      if (filter.op === '=') return numericValue === threshold;
      return true;
    });
  });
  if (state.sortCol !== -1) {
    indices.sort((a, b) => {
      const colIndex = parseInt(state.sortCol, 10);
      const aValue = parseNum(String(DATA.rows[a][colIndex]));
      const bValue = parseNum(String(DATA.rows[b][colIndex]));
      if (aValue === null && bValue === null) return 0;
      if (aValue === null) return 1;
      if (bValue === null) return -1;
      return state.sortDir === 'asc' ? aValue - bValue : bValue - aValue;
    });
  } else {
    indices.sort((a, b) => String(DATA.rows[a][1]).localeCompare(String(DATA.rows[b][1])));
  }
  state.displayIndices = indices;
}

function openFilterPanel() {
  state.pendingFilters = { ...state.filters };
  dom.fpCol.innerHTML = '<option value="">选择指标…</option>';
  FILTER_COLS.forEach(filterCol => {
    const unit = filterCol.unit ? ` (${filterCol.unit})` : '';
    dom.fpCol.innerHTML += `<option value="${filterCol.idx}">${filterCol.name}${unit}</option>`;
  });
  dom.fpCol.value = '';
  dom.fpOp.disabled = true;
  dom.fpVal.disabled = true;
  dom.fpVal.value = '';
  dom.fpUnit.textContent = '';
  dom.fpAddBtn.disabled = true;
  renderFilterChips();
  dom.filterPanel.classList.add('open');
  dom.filterOverlay.classList.add('open');
}

function closeFilterPanel() {
  dom.filterPanel.classList.remove('open');
  dom.filterOverlay.classList.remove('open');
}

function renderFilterChips() {
  const entries = Object.entries(state.pendingFilters);
  if (!entries.length) {
    dom.fpActive.innerHTML = '<span class="fp-empty">暂无筛选条件</span>';
    return;
  }

  dom.fpActive.innerHTML = entries.map(([idx, filter]) => {
    const filterCol = FILTER_COLS.find(col => col.idx === parseInt(idx, 10));
    const opLabel = filter.op === 'empty' ? '为空' : filter.op;
    const valueText = filter.op === 'empty' ? '' : `${filter.val}${filterCol?.unit || ''}`;
    return `<span class="fp-chip">${filterCol?.name} ${opLabel} ${valueText}<button class="fp-chip-rm" data-fidx="${idx}">×</button></span>`;
  }).join('');

  dom.fpActive.querySelectorAll('.fp-chip-rm').forEach(button => {
    button.addEventListener('click', () => {
      delete state.pendingFilters[button.dataset.fidx];
      renderFilterChips();
    });
  });
}

function updateFilterToggleStyle() {
  const hasActiveFilters = Object.keys(state.filters).length > 0;
  dom.filterToggleBtn.classList.toggle('filter-active', hasActiveFilters);
  dom.filterToggleBtn.textContent = hasActiveFilters ? '筛选 ●' : '筛选 ▼';
}

function initFilterPanel(render) {
  dom.fpCol.addEventListener('change', () => {
    const idx = dom.fpCol.value;
    const filterCol = FILTER_COLS.find(col => col.idx === parseInt(idx, 10));
    const hasValue = Boolean(idx);
    dom.fpOp.disabled = !hasValue;
    dom.fpVal.disabled = !hasValue;
    dom.fpVal.value = '';
    dom.fpUnit.textContent = filterCol?.unit || '';
    dom.fpAddBtn.disabled = !hasValue;
  });

  dom.fpOp.addEventListener('change', () => {
    const isEmptyOperator = dom.fpOp.value === 'empty';
    dom.fpVal.disabled = isEmptyOperator;
    if (isEmptyOperator) dom.fpVal.value = '';
  });

  dom.fpAddBtn.addEventListener('click', () => {
    const idx = parseInt(dom.fpCol.value, 10);
    const op = dom.fpOp.value;
    const value = op === 'empty' ? null : parseFloat(dom.fpVal.value);
    if (!idx || !op || (op !== 'empty' && Number.isNaN(value))) return;
    state.pendingFilters[idx] = { op, val: value };
    renderFilterChips();
    dom.fpCol.value = '';
    dom.fpOp.disabled = true;
    dom.fpVal.disabled = true;
    dom.fpVal.value = '';
    dom.fpUnit.textContent = '';
    dom.fpAddBtn.disabled = true;
  });

  dom.fpClearBtn.addEventListener('click', () => {
    state.pendingFilters = {};
    renderFilterChips();
  });

  dom.fpApplyBtn.addEventListener('click', () => {
    state.filters = { ...state.pendingFilters };
    updateFilterToggleStyle();
    closeFilterPanel();
    render();
  });

  dom.filterClose.addEventListener('click', closeFilterPanel);
  dom.filterOverlay.addEventListener('click', closeFilterPanel);
}

window.DashboardFilters = {
  updateIndustryFilter,
  applyFilters,
  openFilterPanel,
  closeFilterPanel,
  renderFilterChips,
  updateFilterToggleStyle,
  initFilterPanel,
};
})();
