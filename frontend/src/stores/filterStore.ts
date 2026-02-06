import { create } from 'zustand';
import type { DashboardFilters, FilterOptions } from '../types';

interface FilterState {
  filters: DashboardFilters;
  options: FilterOptions;
  initialized: boolean;
  setFilter: <K extends keyof DashboardFilters>(key: K, value: DashboardFilters[K]) => void;
  setFilters: (partial: Partial<DashboardFilters>) => void;
  setOptions: (opts: FilterOptions) => void;
  resetFilters: () => void;
  toggleMonth: (month: number) => void;
  toggleContractType: (ct: string) => void;
  toggleConvenio: (convenio: string) => void;
  applyChartFilter: (key: string, value: string) => void;
}

const DEFAULT_FILTERS: DashboardFilters = {
  municipality_code: '280',
  area: 'Salud',
  year: 2025,
  months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
  contract_types: ['HONORARIOS', 'CONTRATA', 'PLANTA'],
  convenios: [],
  search_text: '',
  audit_flag_special: null,
};

function parseUrlFilters(): Partial<DashboardFilters> {
  if (typeof window === 'undefined') return {};
  const params = new URLSearchParams(window.location.search);
  const partial: Partial<DashboardFilters> = {};
  if (params.get('muni')) partial.municipality_code = params.get('muni')!;
  if (params.get('area')) partial.area = params.get('area')!;
  if (params.get('year')) partial.year = parseInt(params.get('year')!);
  if (params.get('months')) partial.months = params.get('months')!.split(',').map(Number);
  if (params.get('ct')) partial.contract_types = params.get('ct')!.split(',');
  if (params.get('conv')) partial.convenios = params.get('conv')!.split(',');
  if (params.get('q')) partial.search_text = params.get('q')!;
  return partial;
}

function syncToUrl(filters: DashboardFilters) {
  if (typeof window === 'undefined') return;
  const params = new URLSearchParams();
  params.set('muni', filters.municipality_code);
  if (filters.area !== 'Salud') params.set('area', filters.area);
  params.set('year', String(filters.year));
  if (filters.months.length < 12) params.set('months', filters.months.join(','));
  if (filters.contract_types.length < 3) params.set('ct', filters.contract_types.join(','));
  if (filters.convenios.length > 0) params.set('conv', filters.convenios.join(','));
  if (filters.search_text) params.set('q', filters.search_text);
  const newUrl = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState(null, '', newUrl);
}

export const useFilterStore = create<FilterState>((set, get) => ({
  filters: { ...DEFAULT_FILTERS, ...parseUrlFilters() },
  options: { months: [], convenios: [], contract_types: [], years: [2025] },
  initialized: false,

  setFilter: (key, value) => {
    set((s) => {
      const newFilters = { ...s.filters, [key]: value };
      syncToUrl(newFilters);
      return { filters: newFilters };
    });
  },

  setFilters: (partial) => {
    set((s) => {
      const newFilters = { ...s.filters, ...partial };
      syncToUrl(newFilters);
      return { filters: newFilters };
    });
  },

  setOptions: (opts) => set({ options: opts, initialized: true }),

  resetFilters: () => {
    const reset = { ...DEFAULT_FILTERS, municipality_code: get().filters.municipality_code };
    syncToUrl(reset);
    set({ filters: reset });
  },

  toggleMonth: (month) => {
    set((s) => {
      const months = s.filters.months.includes(month)
        ? s.filters.months.filter((m) => m !== month)
        : [...s.filters.months, month].sort((a, b) => a - b);
      const newFilters = { ...s.filters, months };
      syncToUrl(newFilters);
      return { filters: newFilters };
    });
  },

  toggleContractType: (ct) => {
    set((s) => {
      const types = s.filters.contract_types.includes(ct)
        ? s.filters.contract_types.filter((t) => t !== ct)
        : [...s.filters.contract_types, ct];
      const newFilters = { ...s.filters, contract_types: types };
      syncToUrl(newFilters);
      return { filters: newFilters };
    });
  },

  toggleConvenio: (convenio) => {
    set((s) => {
      const convs = s.filters.convenios.includes(convenio)
        ? s.filters.convenios.filter((c) => c !== convenio)
        : [...s.filters.convenios, convenio];
      const newFilters = { ...s.filters, convenios: convs };
      syncToUrl(newFilters);
      return { filters: newFilters };
    });
  },

  applyChartFilter: (key, value) => {
    const state = get();
    if (key === 'month') {
      const m = parseInt(value);
      if (!isNaN(m)) state.toggleMonth(m);
    } else if (key === 'convenio') {
      state.toggleConvenio(value);
    } else if (key === 'contract_type') {
      state.toggleContractType(value);
    }
  },
}));
