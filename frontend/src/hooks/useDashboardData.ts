import { useState, useEffect, useCallback } from 'react';
import { useFilterStore } from '../stores/filterStore';
import { fetchKPIs, fetchTimeseries, fetchBreakdown, fetchFilterOptions } from '../services/api';
import type { KPIs, TimeseriesRow, BreakdownRow } from '../types';

export function useDashboardData() {
  const { filters, setOptions } = useFilterStore();
  const [kpis, setKpis] = useState<KPIs | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesRow[]>([]);
  const [timeseriesConvenio, setTimeseriesConvenio] = useState<TimeseriesRow[]>([]);
  const [breakdownConvenio, setBreakdownConvenio] = useState<BreakdownRow[]>([]);
  const [breakdownVinculo, setBreakdownVinculo] = useState<BreakdownRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!filters.municipality_code) return;
    setLoading(true);
    setError(null);
    try {
      const [k, ts, tsConv, bdConv, bdVinc, opts] = await Promise.all([
        fetchKPIs(filters),
        fetchTimeseries(filters, 'month'),
        fetchTimeseries(filters, 'convenio'),
        fetchBreakdown(filters, 'convenio', 10),
        fetchBreakdown(filters, 'vinculo'),
        fetchFilterOptions(filters.municipality_code, filters.area, filters.year),
      ]);
      setKpis(k);
      setTimeseries(ts);
      setTimeseriesConvenio(tsConv);
      setBreakdownConvenio(bdConv);
      setBreakdownVinculo(bdVinc);
      setOptions(opts);
    } catch (e: any) {
      setError(e?.message || 'Error al cargar datos');
    } finally {
      setLoading(false);
    }
  }, [filters, setOptions]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    kpis, timeseries, timeseriesConvenio,
    breakdownConvenio, breakdownVinculo,
    loading, error, refresh,
  };
}
