export interface DashboardFilters {
  municipality_code: string;
  area: string;
  year: number;
  months: number[];
  contract_types: string[];
  convenios: string[];
  search_text: string;
  audit_flag_special: boolean | null;
}

export interface KPIs {
  total_gasto: number;
  gasto_honorarios: number;
  gasto_contrata: number;
  gasto_planta: number;
  count_honorarios: number;
  count_contrata: number;
  count_planta: number;
  unique_profesionales: number;
  unique_convenios: number;
}

export interface TimeseriesRow {
  month: number;
  group_key: string;
  total: number;
  count: number;
  contract_type: string;
}

export interface BreakdownRow {
  group_key: string;
  total: number;
  count: number;
  pct: number;
  unique_people?: number;
}

export interface HonorariosRecord {
  id: number;
  month: number;
  nombre: string;
  rut: string;
  descripcion_funcion: string;
  calificacion_profesional: string;
  fecha_inicio: string;
  fecha_termino: string;
  remuneracion_bruta: number;
  remuneracion_liquida: number;
  monto_total: number;
  observaciones: string;
  convenio: string;
}

export interface ContrataPlantaRecord {
  id: number;
  month: number;
  nombre: string;
  rut: string;
  grado_eus: string;
  cargo: string;
  calificacion_profesional: string;
  region: string;
  asignaciones: number;
  remuneracion_bruta: number;
  remuneracion_liquida: number;
  fecha_inicio: string;
  fecha_termino: string;
  observaciones: string;
  horas: string;
}

export interface PaginatedResponse<T> {
  total: number;
  page: number;
  page_size: number;
  data: T[];
}

export interface FilterOptions {
  months: number[];
  convenios: string[];
  contract_types: string[];
  years: number[];
}

export interface AuditSummary {
  total_exceptions: number;
  by_month: { month: number; count: number; total_diff: number }[];
  by_convenio: { convenio: string; count: number; total_diff: number }[];
  by_cargo: { cargo: string; count: number; total_diff: number }[];
}

export interface AuditExceptionRow {
  id: number;
  month: number;
  contract_type: string;
  record_id: number;
  nombre: string;
  cargo: string;
  convenio: string;
  valor_real: number;
  valor_esperado: number;
  diferencia: number;
  diferencia_pct: number;
  threshold_pct: number;
  match_method: string;
  match_confidence: number;
  fields_used: string[];
  explanation: string;
}

export interface ScrapeRun {
  id: number;
  municipality_code: string;
  area: string;
  year: number;
  months: number[];
  contract_types: string[];
  status: string;
  records_loaded: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
};
