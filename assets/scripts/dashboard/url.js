(() => {
const { DEFAULT_SORT_COL, DEFAULT_SORT_DIR, state } = window.DashboardState;

function updateURLState() {
  const params = new URLSearchParams();
  if (state.sortCol !== DEFAULT_SORT_COL) params.set('sortCol', state.sortCol);
  if (state.sortDir !== DEFAULT_SORT_DIR) params.set('sortDir', state.sortDir);
  if (state.searchText) params.set('q', state.searchText);
  if (state.filterIndustry) params.set('ind', state.filterIndustry);
  if (state.filterStockType) params.set('type', state.filterStockType);
  if (Object.keys(state.filters).length > 0) params.set('f', JSON.stringify(state.filters));

  const queryString = params.toString();
  const nextUrl = window.location.pathname + (queryString ? `?${queryString}` : '');
  window.history.replaceState(null, '', nextUrl);
}

window.DashboardURL = {
  updateURLState,
};
})();
