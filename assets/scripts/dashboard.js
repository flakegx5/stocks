const dom = window.DashboardDOM;
const { COLS } = window.DashboardShared;
const { closeColPicker, initColumnPicker } = window.DashboardColumnPicker;
const {
  applyFilters,
  closeFilterPanel,
  initFilterPanel,
  openFilterPanel,
  updateFilterToggleStyle,
  updateIndustryFilter,
} = window.DashboardFilters;
const {
  buildBody,
  buildHeader,
  cleanColName,
  exportExcel,
  initVirtualScroll,
  isRankMetricName,
  resetVirtualScroll,
  updateSummary,
  updateUpdateTime,
} = window.DashboardView;
const { applyResponsiveDefaults, hydrateStateFromURL, resetViewState, state } = window.DashboardState;
const { updateURLState } = window.DashboardURL;
function render(resetScroll = true) {
  if (resetScroll) resetVirtualScroll();
  updateIndustryFilter();
  applyFilters();
  buildHeader(onSortClick);
  buildBody();
  updateSummary();
  updateURLState();
}

function onSortClick(colIdx) {
  const currentCol = String(colIdx);
  if (String(state.sortCol) === currentCol) {
    state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
  } else {
    state.sortCol = colIdx;
    const col = COLS.find(item => String(item.idx) === currentCol);
    const metric = col ? cleanColName(col.name) : '';
    state.sortDir = isRankMetricName(metric) ? 'asc' : 'desc';
  }
  applyFilters();
  buildHeader(onSortClick);
  buildBody();
  updateSummary();
}

function closeRules() {
  dom.rulesModal.classList.remove('open');
  dom.rulesOverlay.classList.remove('open');
}

function syncQueueButtons() {
  const buttons = Array.from(document.querySelectorAll('.queue-btn'));
  const matched = buttons.find(button => button.getAttribute('data-type') === state.filterStockType);
  if (!matched) {
    state.filterStockType = '非金融股';
  }
  buttons.forEach(button => {
    button.classList.toggle('active', button.getAttribute('data-type') === state.filterStockType);
  });
}

function initEvents() {
  dom.searchBox.addEventListener('input', event => {
    state.searchText = event.target.value.trim();
    render();
  });

  document.querySelectorAll('.queue-btn').forEach(button => {
    button.addEventListener('click', event => {
      state.filterStockType = event.currentTarget.getAttribute('data-type');
      state.filterIndustry = '';
      dom.industryFilter.value = '';
      syncQueueButtons();
      render();
    });
  });

  dom.industryFilter.addEventListener('change', event => {
    state.filterIndustry = event.target.value;
    render();
  });

  dom.filterToggleBtn.addEventListener('click', () => {
    if (dom.filterPanel.classList.contains('open')) closeFilterPanel();
    else openFilterPanel();
  });

  dom.resetView.addEventListener('click', () => {
    resetViewState();
    dom.searchBox.value = '';
    dom.industryFilter.value = '';
    syncQueueButtons();
    closeFilterPanel();
    updateFilterToggleStyle();
    closeColPicker();
    render();
  });

  dom.exportBtn.addEventListener('click', exportExcel);
  dom.rulesBtn.addEventListener('click', () => {
    dom.rulesModal.classList.add('open');
    dom.rulesOverlay.classList.add('open');
  });
  dom.rulesClose.addEventListener('click', closeRules);
  dom.rulesOverlay.addEventListener('click', closeRules);
}

function init() {
  applyResponsiveDefaults();
  hydrateStateFromURL();
  updateUpdateTime();
  dom.searchBox.value = state.searchText;
  syncQueueButtons();
  initColumnPicker(() => {
    buildHeader(onSortClick);
    buildBody();
  });
  initFilterPanel(render);
  initVirtualScroll(buildBody);
  initEvents();
  render();
}

init();
