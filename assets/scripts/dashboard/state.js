(() => {
const {
  COLS,
  PERIODS,
  METRICS,
  COMPUTED_COL_NAMES,
  METRICS_DEFAULT_HIDDEN,
  COMPUTED_DEFAULT_HIDDEN,
  FIXED_DEFAULT_HIDDEN,
  isMobile,
} = window.DashboardShared;

const DEFAULT_SORT_COL = 39;
const DEFAULT_SORT_DIR = 'asc';
const MOBILE_COMPUTED_VISIBLE = new Set(['低估排名', '成长排名', '质量排名', '股东回报排名', '综合排名']);
const FIXED_TOGGLEABLE_NAMES = COLS
  .filter(col => col.group === '基本信息' && !col.locked)
  .map(col => col.name);

const state = {
  sortCol: DEFAULT_SORT_COL,
  sortDir: DEFAULT_SORT_DIR,
  visiblePeriods: new Set(PERIODS),
  visibleMetrics: new Set(METRICS.filter(metric => !METRICS_DEFAULT_HIDDEN.has(metric))),
  visibleComputedCols: new Set(COMPUTED_COL_NAMES.filter(name => !COMPUTED_DEFAULT_HIDDEN.has(name))),
  visibleFixedCols: new Set(FIXED_TOGGLEABLE_NAMES.filter(name => !FIXED_DEFAULT_HIDDEN.has(name))),
  searchText: '',
  filterIndustry: '',
  filterStockType: '非金融股',
  filters: {},
  pendingFilters: {},
  displayIndices: [],
  renderStartIndex: 0,
  renderEndIndex: 50,
  rowHeight: 36,
};

function applyResponsiveDefaults() {
  if (isMobile()) {
    state.visiblePeriods = new Set(PERIODS);
    state.visibleMetrics = new Set();
    state.visibleComputedCols = new Set(MOBILE_COMPUTED_VISIBLE);
    state.visibleFixedCols = new Set(['股票代码']);
    return;
  }

  state.visiblePeriods = new Set(PERIODS);
  state.visibleMetrics = new Set(METRICS.filter(metric => !METRICS_DEFAULT_HIDDEN.has(metric)));
  state.visibleComputedCols = new Set(COMPUTED_COL_NAMES.filter(name => !COMPUTED_DEFAULT_HIDDEN.has(name)));
  state.visibleFixedCols = new Set(FIXED_TOGGLEABLE_NAMES.filter(name => !FIXED_DEFAULT_HIDDEN.has(name)));
}

function resetViewState() {
  state.sortCol = DEFAULT_SORT_COL;
  state.sortDir = DEFAULT_SORT_DIR;
  state.searchText = '';
  state.filterIndustry = '';
  state.filterStockType = '非金融股';
  state.filters = {};
  state.pendingFilters = {};
  applyResponsiveDefaults();
}

function hydrateStateFromURL() {
  const params = new URLSearchParams(window.location.search);
  if (params.has('sortCol')) state.sortCol = parseInt(params.get('sortCol'), 10);
  if (params.has('sortDir')) state.sortDir = params.get('sortDir');
  if (params.has('q')) state.searchText = params.get('q');
  if (params.has('ind')) state.filterIndustry = params.get('ind');
  if (params.has('type')) state.filterStockType = params.get('type');
  if (params.has('f')) {
    try {
      state.filters = JSON.parse(params.get('f'));
    } catch (error) {
      state.filters = {};
    }
  }
}

applyResponsiveDefaults();

window.DashboardState = {
  DEFAULT_SORT_COL,
  DEFAULT_SORT_DIR,
  MOBILE_COMPUTED_VISIBLE,
  FIXED_TOGGLEABLE_NAMES,
  state,
  applyResponsiveDefaults,
  resetViewState,
  hydrateStateFromURL,
};
})();
