import { useState, useEffect, useCallback } from 'react';
import { Row, Col, Card, Spin, Typography, Select } from 'antd';
import { useFilterStore } from '../stores/filterStore';
import { fetchBreakdown, fetchTimeseries } from '../services/api';
import BreakdownChart from '../components/charts/BreakdownChart';
import TimeseriesChart from '../components/charts/TimeseriesChart';
import RecordsTable from '../components/tables/RecordsTable';
import type { BreakdownRow, TimeseriesRow } from '../types';

export default function ConveniosPage() {
  const filters = useFilterStore((s) => s.filters);
  const [breakdown, setBreakdown] = useState<BreakdownRow[]>([]);
  const [topProfesionales, setTopProfesionales] = useState<BreakdownRow[]>([]);
  const [timeseries, setTimeseries] = useState<TimeseriesRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [topN, setTopN] = useState(15);

  const load = useCallback(async () => {
    if (!filters.municipality_code) return;
    setLoading(true);
    try {
      const [bd, tp, ts] = await Promise.all([
        fetchBreakdown(filters, 'convenio', topN),
        fetchBreakdown(filters, 'profesional', topN),
        fetchTimeseries(filters, 'convenio'),
      ]);
      setBreakdown(bd);
      setTopProfesionales(tp);
      setTimeseries(ts);
    } catch { /* ignore */ }
    setLoading(false);
  }, [filters, topN]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>Vista Convenios</Typography.Title>
        <div>
          <Typography.Text style={{ marginRight: 8 }}>Top N:</Typography.Text>
          <Select
            value={topN}
            onChange={setTopN}
            options={[5, 10, 15, 20, 30].map(n => ({ value: n, label: `Top ${n}` }))}
            size="small"
          />
        </div>
      </div>

      <Spin spinning={loading}>
        <Row gutter={[12, 12]}>
          <Col xs={24} lg={12}>
            <BreakdownChart
              data={breakdown}
              title={`Top ${topN} Convenios por Gasto`}
              chartType="bar"
              filterKey="convenio"
            />
          </Col>
          <Col xs={24} lg={12}>
            <BreakdownChart
              data={topProfesionales}
              title={`Top ${topN} Profesionales por Gasto`}
              chartType="bar"
              filterKey="convenio"
            />
          </Col>
        </Row>

        <div style={{ marginTop: 12 }}>
          <TimeseriesChart
            data={timeseries}
            title="Serie Mensual por Convenio"
            groupMode="convenio"
          />
        </div>

        <div style={{ marginTop: 12 }}>
          <RecordsTable contractType="HONORARIOS" />
        </div>
      </Spin>
    </div>
  );
}
