import { Typography, Tabs, Button, Space } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import RecordsTable from '../components/tables/RecordsTable';
import { useFilterStore } from '../stores/filterStore';
import { getExportExcelUrl, getExportCSVUrl } from '../services/api';

export default function RecordsPage() {
  const filters = useFilterStore((s) => s.filters);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>Registros Detalle</Typography.Title>
        <Space>
          <Button
            icon={<DownloadOutlined />}
            href={getExportCSVUrl(filters, 'HONORARIOS')}
            target="_blank"
            size="small"
          >
            CSV Honorarios
          </Button>
          <Button
            icon={<DownloadOutlined />}
            href={getExportCSVUrl(filters, 'CONTRATA')}
            target="_blank"
            size="small"
          >
            CSV Contrata
          </Button>
          <Button
            icon={<DownloadOutlined />}
            href={getExportCSVUrl(filters, 'PLANTA')}
            target="_blank"
            size="small"
          >
            CSV Planta
          </Button>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            href={getExportExcelUrl(filters)}
            target="_blank"
            size="small"
          >
            Excel Consolidado
          </Button>
        </Space>
      </div>

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
  );
}
