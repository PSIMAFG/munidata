import { useState, useEffect, useCallback } from 'react';
import {
  Row, Col, Card, Spin, Typography, Slider, Table, Tag, Statistic, Alert,
} from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { useFilterStore } from '../stores/filterStore';
import { fetchAuditSummary, fetchAuditExceptions } from '../services/api';
import type { AuditSummary, AuditExceptionRow, PaginatedResponse } from '../types';
import { MONTH_NAMES } from '../types';

function formatCLP(value: number | null): string {
  if (value == null) return '-';
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(value);
}

export default function AuditPage() {
  const filters = useFilterStore((s) => s.filters);
  const [threshold, setThreshold] = useState(5);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [exceptions, setExceptions] = useState<PaginatedResponse<AuditExceptionRow> | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    if (!filters.municipality_code) return;
    setLoading(true);
    try {
      const [sum, exc] = await Promise.all([
        fetchAuditSummary(filters.municipality_code, filters.year, threshold),
        fetchAuditExceptions(filters.municipality_code, filters.year, page, 50, undefined, undefined, threshold),
      ]);
      setSummary(sum);
      setExceptions(exc);
    } catch { /* ignore */ }
    setLoading(false);
  }, [filters.municipality_code, filters.year, threshold, page]);

  useEffect(() => { load(); }, [load]);

  const columns = [
    {
      title: 'Mes', dataIndex: 'month', width: 70,
      render: (m: number) => MONTH_NAMES[m]?.substring(0, 3) || m,
    },
    { title: 'Nombre', dataIndex: 'nombre', width: 180, ellipsis: true },
    { title: 'Cargo', dataIndex: 'cargo', width: 150, ellipsis: true },
    {
      title: 'Convenio', dataIndex: 'convenio', width: 120,
      render: (c: string) => c ? <Tag color="blue">{c}</Tag> : '-',
    },
    {
      title: 'Valor Real', dataIndex: 'valor_real', width: 120, align: 'right' as const,
      render: formatCLP,
    },
    {
      title: 'Valor Esperado', dataIndex: 'valor_esperado', width: 120, align: 'right' as const,
      render: formatCLP,
    },
    {
      title: 'Diferencia', dataIndex: 'diferencia', width: 120, align: 'right' as const,
      render: (v: number) => (
        <span style={{ color: v > 0 ? '#f5222d' : '#52c41a' }}>{formatCLP(v)}</span>
      ),
    },
    {
      title: 'Dif. %', dataIndex: 'diferencia_pct', width: 80, align: 'right' as const,
      render: (v: number) => (
        <Tag color={Math.abs(v) > 20 ? 'red' : Math.abs(v) > 10 ? 'orange' : 'gold'}>
          {v?.toFixed(1)}%
        </Tag>
      ),
    },
    { title: 'Método', dataIndex: 'match_method', width: 120, ellipsis: true },
    {
      title: 'Confianza', dataIndex: 'match_confidence', width: 80,
      render: (v: number) => v != null ? `${(v * 100).toFixed(0)}%` : '-',
    },
    { title: 'Explicación', dataIndex: 'explanation', width: 250, ellipsis: true },
  ];

  const byMonthOption = summary ? {
    tooltip: { trigger: 'axis' as const },
    xAxis: {
      type: 'category' as const,
      data: summary.by_month.map(d => MONTH_NAMES[d.month]?.substring(0, 3) || d.month),
    },
    yAxis: { type: 'value' as const },
    series: [{
      type: 'bar' as const,
      data: summary.by_month.map(d => d.count),
      itemStyle: { color: '#faad14' },
    }],
    grid: { left: 40, right: 20, top: 10, bottom: 30 },
  } : {};

  const byConvenioOption = summary ? {
    tooltip: { trigger: 'axis' as const },
    yAxis: {
      type: 'category' as const,
      data: summary.by_convenio.map(d => d.convenio),
      axisLabel: { fontSize: 10, width: 100, overflow: 'truncate' as const },
      inverse: true,
    },
    xAxis: { type: 'value' as const },
    series: [{
      type: 'bar' as const,
      data: summary.by_convenio.map(d => d.count),
      itemStyle: { color: '#f5222d' },
    }],
    grid: { left: 120, right: 20, top: 10, bottom: 20 },
  } : {};

  return (
    <div>
      <Typography.Title level={3}>
        <WarningOutlined style={{ color: '#faad14', marginRight: 8 }} />
        Auditoría de Remuneraciones
      </Typography.Title>

      <Card size="small" style={{ marginBottom: 12 }}>
        <Row align="middle" gutter={16}>
          <Col span={4}>
            <Typography.Text strong>Umbral de alerta:</Typography.Text>
          </Col>
          <Col span={12}>
            <Slider
              min={1}
              max={50}
              value={threshold}
              onChange={setThreshold}
              marks={{ 5: '5%', 10: '10%', 20: '20%', 50: '50%' }}
            />
          </Col>
          <Col span={4}>
            <Typography.Text>{threshold}%</Typography.Text>
          </Col>
          <Col span={4}>
            <Statistic
              title="Excepciones"
              value={summary?.total_exceptions ?? 0}
              valueStyle={{ color: '#f5222d' }}
            />
          </Col>
        </Row>
      </Card>

      {(!summary || summary.total_exceptions === 0) && !loading && (
        <Alert
          type="info"
          showIcon
          message="Sin excepciones de auditoría"
          description="No se encontraron registros que excedan el umbral configurado. Esto puede deberse a que aún no se han ejecutado las reglas de auditoría, o a que no hay datos cargados. Ejecute la extracción desde Setup y luego el módulo de auditoría."
          style={{ marginBottom: 12 }}
        />
      )}

      <Spin spinning={loading}>
        <Row gutter={[12, 12]}>
          <Col xs={24} lg={12}>
            <Card size="small" title="Alertas por Mes">
              {summary && summary.by_month.length > 0 ? (
                <ReactECharts option={byMonthOption} style={{ height: 200 }} notMerge />
              ) : (
                <Typography.Text type="secondary">Sin datos</Typography.Text>
              )}
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card size="small" title="Alertas por Convenio">
              {summary && summary.by_convenio.length > 0 ? (
                <ReactECharts
                  option={byConvenioOption}
                  style={{ height: Math.max(200, (summary.by_convenio.length) * 28 + 40) }}
                  notMerge
                />
              ) : (
                <Typography.Text type="secondary">Sin datos</Typography.Text>
              )}
            </Card>
          </Col>
        </Row>

        <Card size="small" title="Detalle de Excepciones" style={{ marginTop: 12 }}>
          <Table
            columns={columns}
            dataSource={exceptions?.data || []}
            rowKey="id"
            size="small"
            scroll={{ x: 1400 }}
            pagination={{
              current: page,
              pageSize: 50,
              total: exceptions?.total || 0,
              onChange: setPage,
              showTotal: (t) => `${t} excepciones`,
            }}
          />
        </Card>
      </Spin>
    </div>
  );
}
