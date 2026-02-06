import { Row, Col, Alert, Spin, Button } from 'antd';
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons';
import KPICards from '../components/dashboard/KPICards';
import TimeseriesChart from '../components/charts/TimeseriesChart';
import BreakdownChart from '../components/charts/BreakdownChart';
import RecordsTable from '../components/tables/RecordsTable';
import { useDashboardData } from '../hooks/useDashboardData';
import { useFilterStore } from '../stores/filterStore';
import { getExportExcelUrl } from '../services/api';

export default function DashboardPage() {
  const filters = useFilterStore((s) => s.filters);
  const {
    kpis, timeseries, timeseriesConvenio,
    breakdownConvenio, breakdownVinculo,
    loading, error, refresh,
  } = useDashboardData();

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>
          Dashboard - MU{parseInt(filters.municipality_code || '0').toString().padStart(3, '0')} - {filters.area} {filters.year}
        </h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button icon={<ReloadOutlined />} onClick={refresh} loading={loading}>
            Actualizar
          </Button>
          <Button icon={<DownloadOutlined />} href={getExportExcelUrl(filters)} target="_blank">
            Export Excel
          </Button>
        </div>
      </div>

      {error && <Alert type="error" message={error} style={{ marginBottom: 12 }} closable />}

      <Spin spinning={loading}>
        {/* KPI Cards */}
        <KPICards kpis={kpis} loading={loading} />

        {/* Charts Row 1: Timeseries */}
        <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
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
              title="Participación por Calidad Contractual"
              chartType="pie"
              filterKey="contract_type"
            />
          </Col>
        </Row>

        {/* Charts Row 2: Convenios */}
        <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
          <Col xs={24} lg={14}>
            <TimeseriesChart
              data={timeseriesConvenio}
              title="Honorarios por Convenio - Mensual"
              groupMode="convenio"
            />
          </Col>
          <Col xs={24} lg={10}>
            <BreakdownChart
              data={breakdownConvenio}
              title="Top 10 Convenios (Honorarios)"
              chartType="bar"
              filterKey="convenio"
            />
          </Col>
        </Row>

        {/* Detail Table */}
        <div style={{ marginTop: 12 }}>
          <RecordsTable contractType="HONORARIOS" compact />
        </div>
      </Spin>
    </div>
  );
}
