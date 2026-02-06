import axios from 'axios';
import type {
  DashboardFilters, KPIs, TimeseriesRow, BreakdownRow,
  PaginatedResponse, HonorariosRecord, ContrataPlantaRecord,
  FilterOptions, AuditSummary, AuditExceptionRow, ScrapeRun
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '';

const api = axios.create({ baseURL: API_BASE });

function filtersToParams(f: DashboardFilters): Record<string, string> {
  const params: Record<string, string> = {
    municipality_code: f.municipality_code,
    area: f.area,
    year: String(f.year),
  };
  if (f.months.length > 0 && f.months.length < 12) {
    params.months = f.months.join(',');
  }
  if (f.contract_types.length > 0 && f.contract_types.length < 3) {
    params.contract_types = f.contract_types.join(',');
  }
  if (f.convenios.length > 0) {
    params.convenios = f.convenios.join(',');
  }
  if (f.search_text) {
    params.search_text = f.search_text;
  }
  return params;
}

export async function fetchKPIs(f: DashboardFilters): Promise<KPIs> {
  const { data } = await api.get('/api/dashboard/kpis', { params: filtersToParams(f) });
  return data;
}

export async function fetchTimeseries(f: DashboardFilters, group_by: string = 'month'): Promise<TimeseriesRow[]> {
  const { data } = await api.get('/api/dashboard/timeseries', {
    params: { ...filtersToParams(f), group_by },
  });
  return data;
}

export async function fetchBreakdown(f: DashboardFilters, group_by: string = 'convenio', top_n: number = 10): Promise<BreakdownRow[]> {
  const { data } = await api.get('/api/dashboard/breakdown', {
    params: { ...filtersToParams(f), group_by, top_n },
  });
  return data;
}

export async function fetchHonorarios(
  f: DashboardFilters, page: number = 1, page_size: number = 50,
  sort_by?: string, sort_desc?: boolean
): Promise<PaginatedResponse<HonorariosRecord>> {
  const params: Record<string, string> = {
    ...filtersToParams(f), page: String(page), page_size: String(page_size),
  };
  if (sort_by) params.sort_by = sort_by;
  if (sort_desc) params.sort_desc = 'true';
  const { data } = await api.get('/api/records/honorarios', { params });
  return data;
}

export async function fetchContrata(
  f: DashboardFilters, page: number = 1, page_size: number = 50,
  sort_by?: string, sort_desc?: boolean
): Promise<PaginatedResponse<ContrataPlantaRecord>> {
  const params: Record<string, string> = {
    ...filtersToParams(f), page: String(page), page_size: String(page_size),
  };
  if (sort_by) params.sort_by = sort_by;
  if (sort_desc) params.sort_desc = 'true';
  const { data } = await api.get('/api/records/contrata', { params });
  return data;
}

export async function fetchPlanta(
  f: DashboardFilters, page: number = 1, page_size: number = 50,
  sort_by?: string, sort_desc?: boolean
): Promise<PaginatedResponse<ContrataPlantaRecord>> {
  const params: Record<string, string> = {
    ...filtersToParams(f), page: String(page), page_size: String(page_size),
  };
  if (sort_by) params.sort_by = sort_by;
  if (sort_desc) params.sort_desc = 'true';
  const { data } = await api.get('/api/records/planta', { params });
  return data;
}

export async function fetchFilterOptions(municipality_code: string, area: string = 'Salud', year: number = 2025): Promise<FilterOptions> {
  const { data } = await api.get('/api/filters/options', {
    params: { municipality_code, area, year },
  });
  return data;
}

export async function fetchAuditSummary(municipality_code: string, year: number = 2025, threshold_pct?: number): Promise<AuditSummary> {
  const params: Record<string, string> = { municipality_code, year: String(year) };
  if (threshold_pct !== undefined) params.threshold_pct = String(threshold_pct);
  const { data } = await api.get('/api/audit/summary', { params });
  return data;
}

export async function fetchAuditExceptions(
  municipality_code: string, year: number = 2025,
  page: number = 1, page_size: number = 50,
  month?: number, convenio?: string, threshold_pct?: number
): Promise<PaginatedResponse<AuditExceptionRow>> {
  const params: Record<string, string> = {
    municipality_code, year: String(year), page: String(page), page_size: String(page_size),
  };
  if (month) params.month = String(month);
  if (convenio) params.convenio = convenio;
  if (threshold_pct !== undefined) params.threshold_pct = String(threshold_pct);
  const { data } = await api.get('/api/audit/exceptions', { params });
  return data;
}

export async function createScrapeRun(req: {
  municipality_code: string; area?: string; year?: number;
  months?: number[]; kinds?: string[];
}) {
  const { data } = await api.post('/api/scrape-runs', req);
  return data;
}

export async function fetchScrapeRuns(municipality_code?: string): Promise<ScrapeRun[]> {
  const params: Record<string, string> = {};
  if (municipality_code) params.municipality_code = municipality_code;
  const { data } = await api.get('/api/scrape-runs', { params });
  return data;
}

export async function fetchScrapeRun(id: number): Promise<ScrapeRun> {
  const { data } = await api.get(`/api/scrape-runs/${id}`);
  return data;
}

export function getExportCSVUrl(f: DashboardFilters, contract_type: string): string {
  const params = new URLSearchParams({
    ...filtersToParams(f),
    contract_type,
  });
  return `${API_BASE}/api/export/csv?${params}`;
}

export function getExportExcelUrl(f: DashboardFilters): string {
  const params = new URLSearchParams(filtersToParams(f));
  return `${API_BASE}/api/export/excel?${params}`;
}
