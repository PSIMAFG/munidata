import { useState, useEffect, useCallback } from 'react';
import { Row, Col, Spin, Typography, Tabs } from 'antd';
import { useFilterStore } from '../stores/filterStore';
import { fetchBreakdown, fetchTimeseries } from '../services/api';
import BreakdownChart from '../components/charts/BreakdownChart';
import TimeseriesChart from '../components/charts/TimeseriesChart';
import RecordsTable from '../components/tables/RecordsTable';
import type { BreakdownRow, TimeseriesRow } from '../types';

export default function ContractTypePage() {
  const filters = useFilterStore((s) => s.filters);
  const [breakdownVinculo, setBreakdownVinculo] = useState<BreakdownRow[]>([]);
  const [timeseries, setTimeseries] = useState<TimeseriesRow[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!filters.municipality_code) return;
    setLoading(true);
    try {
      const [bd, ts] = await Promise.all([
        fetchBreakdown(filters, 'vinculo'),
        fetchTimeseries(filters, 'month'),
      ]);
      setBreakdownVinculo(bd);
      setTimeseries(ts);
    } catch { /* ignore */ }
    setLoading(false);
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <Typography.Title level={3}>Calidad Contractual - Honorarios vs Contrata vs Planta</Typography.Title>

      <Spin spinning={loading}>
        <Row gutter={[12, 12]}>
          <Col xs={24} lg={14}>
            <TimeseriesChart
              data={timeseries}
              title="Gasto Mensual por Tipo de Vínculo"
              groupMode="contract_type"
            />
          </Col>
          <Col xs={24} lg={10}>
            <BreakdownChart
              data={breakdownVinculo}
              title="Distribución por Calidad Contractual"
              chartType="pie"
              filterKey="contract_type"
            />
          </Col>
        </Row>

        <div style={{ marginTop: 16 }}>
          <Tabs
            defaultActiveKey="HONORARIOS"
            items={[
              {
                key: 'HONORARIOS',
                label: 'Honorarios',
                children: <RecordsTable contractType="HONORARIOS" />,
              },
              {
                key: 'CONTRATA',
                label: 'Contrata',
                children: <RecordsTable contractType="CONTRATA" />,
              },
              {
                key: 'PLANTA',
                label: 'Planta',
                children: <RecordsTable contractType="PLANTA" />,
              },
            ]}
          />
        </div>
      </Spin>
    </div>
  );
}
