import { useState, useEffect, useCallback } from 'react';
import { Table, Card, Tag, Input, Space, Button } from 'antd';
import { DownloadOutlined, SearchOutlined } from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { useFilterStore } from '../../stores/filterStore';
import { fetchHonorarios, fetchContrata, fetchPlanta, getExportCSVUrl } from '../../services/api';
import type { HonorariosRecord, ContrataPlantaRecord } from '../../types';
import { MONTH_NAMES } from '../../types';

function formatCLP(value: number | null): string {
  if (value == null) return '-';
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(value);
}

interface Props {
  contractType: 'HONORARIOS' | 'CONTRATA' | 'PLANTA';
  compact?: boolean;
}

export default function RecordsTable({ contractType, compact = false }: Props) {
  const filters = useFilterStore((s) => s.filters);
  const [data, setData] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(compact ? 10 : 50);
  const [sortBy, setSortBy] = useState<string | undefined>();
  const [sortDesc, setSortDesc] = useState(false);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      let result;
      if (contractType === 'HONORARIOS') {
        result = await fetchHonorarios(filters, page, pageSize, sortBy, sortDesc);
      } else if (contractType === 'CONTRATA') {
        result = await fetchContrata(filters, page, pageSize, sortBy, sortDesc);
      } else {
        result = await fetchPlanta(filters, page, pageSize, sortBy, sortDesc);
      }
      setData(result.data);
      setTotal(result.total);
    } catch {
      setData([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filters, page, pageSize, sortBy, sortDesc, contractType]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [filters]);

  const honorariosColumns: ColumnsType<HonorariosRecord> = [
    {
      title: 'Mes', dataIndex: 'month', width: 70, sorter: true,
      render: (m: number) => MONTH_NAMES[m]?.substring(0, 3) || m,
    },
    { title: 'Nombre', dataIndex: 'nombre', width: 180, ellipsis: true, sorter: true },
    { title: 'Función', dataIndex: 'descripcion_funcion', width: 150, ellipsis: true },
    { title: 'Calificación', dataIndex: 'calificacion_profesional', width: 120, ellipsis: true },
    {
      title: 'Rem. Bruta', dataIndex: 'remuneracion_bruta', width: 120, sorter: true, align: 'right',
      render: formatCLP,
    },
    {
      title: 'Rem. Líquida', dataIndex: 'remuneracion_liquida', width: 120, sorter: true, align: 'right',
      render: formatCLP,
    },
    {
      title: 'Convenio', dataIndex: 'convenio', width: 120,
      render: (c: string) => c ? <Tag color="blue">{c}</Tag> : <Tag>-</Tag>,
    },
    { title: 'Observaciones', dataIndex: 'observaciones', width: 200, ellipsis: true },
  ];

  const cpColumns: ColumnsType<ContrataPlantaRecord> = [
    {
      title: 'Mes', dataIndex: 'month', width: 70, sorter: true,
      render: (m: number) => MONTH_NAMES[m]?.substring(0, 3) || m,
    },
    { title: 'Nombre', dataIndex: 'nombre', width: 180, ellipsis: true, sorter: true },
    { title: 'Grado', dataIndex: 'grado_eus', width: 70 },
    { title: 'Cargo', dataIndex: 'cargo', width: 150, ellipsis: true },
    { title: 'Calificación', dataIndex: 'calificacion_profesional', width: 120, ellipsis: true },
    {
      title: 'Rem. Bruta', dataIndex: 'remuneracion_bruta', width: 120, sorter: true, align: 'right',
      render: formatCLP,
    },
    {
      title: 'Rem. Líquida', dataIndex: 'remuneracion_liquida', width: 120, sorter: true, align: 'right',
      render: formatCLP,
    },
    { title: 'Horas', dataIndex: 'horas', width: 70 },
    { title: 'Observaciones', dataIndex: 'observaciones', width: 200, ellipsis: true },
  ];

  const columns = contractType === 'HONORARIOS' ? honorariosColumns : cpColumns;

  const handleTableChange = (
    pagination: TablePaginationConfig,
    _filters: any,
    sorter: any,
  ) => {
    setPage(pagination.current || 1);
    setPageSize(pagination.pageSize || 50);
    if (sorter.field) {
      setSortBy(sorter.field as string);
      setSortDesc(sorter.order === 'descend');
    } else {
      setSortBy(undefined);
      setSortDesc(false);
    }
  };

  return (
    <Card
      size="small"
      title={`Registros ${contractType}`}
      extra={
        <Button
          size="small"
          icon={<DownloadOutlined />}
          href={getExportCSVUrl(filters, contractType)}
          target="_blank"
        >
          CSV
        </Button>
      }
    >
      <Table
        columns={columns as any}
        dataSource={data}
        rowKey="id"
        loading={loading}
        size="small"
        scroll={{ x: 900 }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: !compact,
          showTotal: (t) => `${t} registros`,
          pageSizeOptions: ['10', '25', '50', '100'],
          size: 'small',
        }}
        onChange={handleTableChange}
      />
    </Card>
  );
}
