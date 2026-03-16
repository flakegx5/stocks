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
let mobileTouchY = null;

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

function shouldLockTableScroll() {
  if (!dom.tableWrap || !dom.pageHeader || window.innerWidth >= 768) return false;
  const headerBottom = dom.pageHeader.getBoundingClientRect().bottom;
  const tableTop = dom.tableWrap.getBoundingClientRect().top;
  return tableTop <= headerBottom + 4;
}

function syncMobileTableScrollMode(forceUnlock = false) {
  if (!dom.tableWrap) return;
  if (window.innerWidth >= 768 || forceUnlock) {
    dom.tableWrap.classList.remove('table-scroll-active');
    return;
  }
  dom.tableWrap.classList.toggle('table-scroll-active', shouldLockTableScroll());
}

function routeTouchToTable(deltaY) {
  if (!dom.tableWrap) return;
  const nextScrollTop = dom.tableWrap.scrollTop - deltaY;
  dom.tableWrap.scrollTop = Math.max(0, nextScrollTop);
}

function initMobileTableScrollMode() {
  if (!dom.tableWrap) return;

  const requestSync = () => window.requestAnimationFrame(() => syncMobileTableScrollMode(false));
  window.addEventListener('scroll', requestSync, { passive: true });
  window.addEventListener('resize', () => syncMobileTableScrollMode(true), { passive: true });

  dom.tableWrap.addEventListener('touchstart', event => {
    if (window.innerWidth >= 768) return;
    mobileTouchY = event.touches[0]?.clientY ?? null;
    syncMobileTableScrollMode(false);
  }, { passive: true });

  dom.tableWrap.addEventListener('touchmove', event => {
    if (window.innerWidth >= 768 || mobileTouchY === null) return;
    const currentY = event.touches[0]?.clientY;
    if (typeof currentY !== 'number') return;
    const deltaY = currentY - mobileTouchY;
    mobileTouchY = currentY;

    const isActive = dom.tableWrap.classList.contains('table-scroll-active');
    if (!isActive) {
      if (deltaY < 0 && shouldLockTableScroll()) {
        dom.tableWrap.classList.add('table-scroll-active');
        event.preventDefault();
        routeTouchToTable(deltaY);
      }
      return;
    }

    if (deltaY > 0 && dom.tableWrap.scrollTop <= 0) {
      dom.tableWrap.classList.remove('table-scroll-active');
      return;
    }

    event.preventDefault();
    routeTouchToTable(deltaY);
  }, { passive: false });

  dom.tableWrap.addEventListener('touchend', () => {
    mobileTouchY = null;
    syncMobileTableScrollMode(false);
  }, { passive: true });

  requestSync();
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
  initMobileTableScrollMode();
  render();
}

init();
