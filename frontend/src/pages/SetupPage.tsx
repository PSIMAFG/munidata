import { useState, useEffect, useCallback } from 'react';
import {
  Card, Input, Select, Button, Space, Typography, Row, Col,
  Table, Tag, Alert, Checkbox, InputNumber,
} from 'antd';
import { PlayCircleOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons';
import { useFilterStore } from '../stores/filterStore';
import { createScrapeRun, fetchScrapeRuns, fetchScrapeRun } from '../services/api';
import type { ScrapeRun } from '../types';

const STATUS_COLORS: Record<string, string> = {
  PENDING: 'default',
  RUNNING: 'processing',
  COMPLETED: 'success',
  FAILED: 'error',
};

export default function SetupPage() {
  const { filters, setFilter } = useFilterStore();
  const [runs, setRuns] = useState<ScrapeRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [months, setMonths] = useState<number[]>([1,2,3,4,5,6,7,8,9,10,11,12]);
  const [kinds, setKinds] = useState<string[]>(['honorarios', 'contrata', 'planta', 'escalas']);
  const [submitting, setSubmitting] = useState(false);

  const loadRuns = useCallback(async () => {
    try {
      const data = await fetchScrapeRuns(filters.municipality_code);
      setRuns(data);
    } catch { /* ignore */ }
  }, [filters.municipality_code]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  const handleScrape = async () => {
    setSubmitting(true);
    try {
      await createScrapeRun({
        municipality_code: filters.municipality_code,
        area: filters.area,
        year: filters.year,
        months,
        kinds,
      });
      await loadRuns();
    } catch (e: any) {
      console.error(e);
    } finally {
      setSubmitting(false);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 50 },
    {
      title: 'Estado', dataIndex: 'status', width: 100,
      render: (s: string) => <Tag color={STATUS_COLORS[s] || 'default'}>{s}</Tag>,
    },
    { title: 'Tipos', dataIndex: 'contract_types', width: 200,
      render: (v: string[]) => v?.map(t => <Tag key={t}>{t}</Tag>),
    },
    { title: 'Registros', dataIndex: 'records_loaded', width: 100 },
    { title: 'Error', dataIndex: 'error_message', ellipsis: true },
    { title: 'Creado', dataIndex: 'created_at', width: 170 },
  ];

  return (
    <div>
      <Typography.Title level={3}>Setup - Configuración de Extracción</Typography.Title>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card title="Configuración" size="small">
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <div>
                <Typography.Text strong>Código Municipio</Typography.Text>
                <Input
                  value={filters.municipality_code}
                  onChange={(e) => setFilter('municipality_code', e.target.value)}
                  placeholder="Ej: 280 (San Antonio)"
                  addonBefore="MU"
                />
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  Se genera org=MU{parseInt(filters.municipality_code || '0').toString().padStart(3, '0')}
                </Typography.Text>
              </div>

              <div>
                <Typography.Text strong>Área</Typography.Text>
                <Select
                  value={filters.area}
                  onChange={(v) => setFilter('area', v)}
                  options={[
                    { value: 'Salud', label: 'Salud' },
                    { value: 'Educación', label: 'Educación' },
                  ]}
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <Typography.Text strong>Año</Typography.Text>
                <InputNumber
                  value={filters.year}
                  onChange={(v) => setFilter('year', v || 2025)}
                  min={2020}
                  max={2026}
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <Typography.Text strong>Meses a Extraer</Typography.Text>
                <Checkbox.Group
                  value={months}
                  onChange={(v) => setMonths(v as number[])}
                  options={[1,2,3,4,5,6,7,8,9,10,11,12].map(m => ({
                    value: m,
                    label: ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][m-1],
                  }))}
                />
              </div>

              <div>
                <Typography.Text strong>Tipos de Datos</Typography.Text>
                <Checkbox.Group
                  value={kinds}
                  onChange={(v) => setKinds(v as string[])}
                  options={[
                    { value: 'honorarios', label: 'Honorarios' },
                    { value: 'contrata', label: 'Contrata' },
                    { value: 'planta', label: 'Planta' },
                    { value: 'escalas', label: 'Escalas Remuneraciones' },
                  ]}
                />
              </div>

              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleScrape}
                loading={submitting}
                block
                size="large"
              >
                Iniciar Extracción
              </Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card
            title="Historial de Extracciones"
            size="small"
            extra={
              <Button size="small" icon={<ReloadOutlined />} onClick={loadRuns}>
                Actualizar
              </Button>
            }
          >
            <Table
              columns={columns}
              dataSource={runs}
              rowKey="id"
              size="small"
              pagination={{ pageSize: 10 }}
              scroll={{ x: 600 }}
            />
          </Card>
        </Col>
      </Row>

      <Alert
        type="info"
        showIcon
        style={{ marginTop: 16 }}
        message="Instrucciones"
        description={
          <ol style={{ margin: 0, paddingLeft: 20 }}>
            <li>Ingrese el código del municipio (ej: 280 para San Antonio)</li>
            <li>Seleccione área, año y meses</li>
            <li>Presione "Iniciar Extracción" para lanzar el scraper</li>
            <li>El proceso corre en background (Celery). Refresque para ver estado</li>
            <li>Una vez completado, vaya a Dashboard para ver las visualizaciones</li>
          </ol>
        }
      />
    </div>
  );
}
