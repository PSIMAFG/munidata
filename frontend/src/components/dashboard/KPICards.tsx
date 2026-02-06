import { Row, Col, Card, Statistic, Skeleton } from 'antd';
import {
  DollarOutlined, TeamOutlined, FileTextOutlined, BankOutlined,
} from '@ant-design/icons';
import type { KPIs } from '../../types';

function formatCLP(value: number): string {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(value);
}

function formatNum(value: number): string {
  return new Intl.NumberFormat('es-CL').format(value);
}

interface Props {
  kpis: KPIs | null;
  loading: boolean;
}

export default function KPICards({ kpis, loading }: Props) {
  if (loading || !kpis) {
    return (
      <Row gutter={[12, 12]}>
        {[1,2,3,4,5,6].map(i => (
          <Col xs={12} sm={8} md={4} key={i}>
            <Card size="small"><Skeleton active paragraph={false} /></Card>
          </Col>
        ))}
      </Row>
    );
  }

  const cards = [
    {
      title: 'Gasto Total',
      value: formatCLP(kpis.total_gasto),
      icon: <DollarOutlined />,
      color: '#1677ff',
    },
    {
      title: 'Honorarios',
      value: formatCLP(kpis.gasto_honorarios),
      suffix: `(${formatNum(kpis.count_honorarios)} reg.)`,
      color: '#1677ff',
    },
    {
      title: 'Contrata',
      value: formatCLP(kpis.gasto_contrata),
      suffix: `(${formatNum(kpis.count_contrata)} reg.)`,
      color: '#52c41a',
    },
    {
      title: 'Planta',
      value: formatCLP(kpis.gasto_planta),
      suffix: `(${formatNum(kpis.count_planta)} reg.)`,
      color: '#faad14',
    },
    {
      title: 'Profesionales',
      value: formatNum(kpis.unique_profesionales),
      icon: <TeamOutlined />,
      color: '#722ed1',
    },
    {
      title: 'Convenios',
      value: formatNum(kpis.unique_convenios),
      icon: <BankOutlined />,
      color: '#13c2c2',
    },
  ];

  return (
    <Row gutter={[12, 12]}>
      {cards.map((c, i) => (
        <Col xs={12} sm={8} md={4} key={i}>
          <Card
            size="small"
            style={{ borderTop: `3px solid ${c.color}` }}
            bodyStyle={{ padding: '12px' }}
          >
            <div style={{ fontSize: 11, color: '#8c8c8c', marginBottom: 4 }}>{c.title}</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: c.color }}>{c.value}</div>
            {c.suffix && <div style={{ fontSize: 11, color: '#8c8c8c' }}>{c.suffix}</div>}
          </Card>
        </Col>
      ))}
    </Row>
  );
}
