import { useFilterStore } from '../../stores/filterStore';
import { Input, Select, Checkbox, Typography, Divider, Button, Space, Tag } from 'antd';
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import { MONTH_NAMES } from '../../types';

const CONTRACT_TYPE_COLORS: Record<string, string> = {
  HONORARIOS: '#1677ff',
  CONTRATA: '#52c41a',
  PLANTA: '#faad14',
};

export default function FilterPanel() {
  const {
    filters, options, setFilter, resetFilters,
    toggleMonth, toggleContractType, toggleConvenio,
  } = useFilterStore();

  return (
    <div style={{ padding: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={5} style={{ margin: 0 }}>Filtros</Typography.Title>
        <Button size="small" icon={<ReloadOutlined />} onClick={resetFilters}>Reset</Button>
      </div>

      {/* Municipality Code */}
      <div style={{ marginBottom: 16 }}>
        <Typography.Text strong style={{ fontSize: 12 }}>Municipio (Código)</Typography.Text>
        <Input
          value={filters.municipality_code}
          onChange={(e) => setFilter('municipality_code', e.target.value)}
          placeholder="Ej: 280"
          style={{ marginTop: 4 }}
          size="small"
        />
      </div>

      {/* Year */}
      <div style={{ marginBottom: 16 }}>
        <Typography.Text strong style={{ fontSize: 12 }}>Año</Typography.Text>
        <Select
          value={filters.year}
          onChange={(v) => setFilter('year', v)}
          options={(options.years.length > 0 ? options.years : [2025, 2024, 2023]).map(y => ({ value: y, label: String(y) }))}
          style={{ width: '100%', marginTop: 4 }}
          size="small"
        />
      </div>

      <Divider style={{ margin: '8px 0' }} />

      {/* Months */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography.Text strong style={{ fontSize: 12 }}>Meses</Typography.Text>
          <Space size={4}>
            <Typography.Text
              style={{ fontSize: 11, cursor: 'pointer', color: '#1677ff' }}
              onClick={() => setFilter('months', [1,2,3,4,5,6,7,8,9,10,11,12])}
            >Todos</Typography.Text>
            <Typography.Text
              style={{ fontSize: 11, cursor: 'pointer', color: '#1677ff' }}
              onClick={() => setFilter('months', [])}
            >Ninguno</Typography.Text>
          </Space>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
          {[1,2,3,4,5,6,7,8,9,10,11,12].map(m => (
            <Tag
              key={m}
              color={filters.months.includes(m) ? 'blue' : undefined}
              style={{ cursor: 'pointer', margin: 0, fontSize: 11 }}
              onClick={() => toggleMonth(m)}
            >
              {MONTH_NAMES[m]?.substring(0, 3)}
            </Tag>
          ))}
        </div>
      </div>

      <Divider style={{ margin: '8px 0' }} />

      {/* Contract Types */}
      <div style={{ marginBottom: 16 }}>
        <Typography.Text strong style={{ fontSize: 12 }}>Tipo de Vínculo</Typography.Text>
        <div style={{ marginTop: 4 }}>
          {['HONORARIOS', 'CONTRATA', 'PLANTA'].map(ct => (
            <div key={ct} style={{ marginBottom: 2 }}>
              <Checkbox
                checked={filters.contract_types.includes(ct)}
                onChange={() => toggleContractType(ct)}
              >
                <Tag color={CONTRACT_TYPE_COLORS[ct]} style={{ margin: 0 }}>{ct}</Tag>
              </Checkbox>
            </div>
          ))}
        </div>
      </div>

      <Divider style={{ margin: '8px 0' }} />

      {/* Convenios */}
      <div style={{ marginBottom: 16 }}>
        <Typography.Text strong style={{ fontSize: 12 }}>Convenios</Typography.Text>
        <Select
          mode="multiple"
          value={filters.convenios}
          onChange={(v) => setFilter('convenios', v)}
          options={options.convenios.map(c => ({ value: c, label: c }))}
          style={{ width: '100%', marginTop: 4 }}
          size="small"
          placeholder="Todos"
          allowClear
          maxTagCount={3}
        />
      </div>

      <Divider style={{ margin: '8px 0' }} />

      {/* Search */}
      <div style={{ marginBottom: 16 }}>
        <Typography.Text strong style={{ fontSize: 12 }}>Buscar Profesional/Cargo</Typography.Text>
        <Input
          value={filters.search_text}
          onChange={(e) => setFilter('search_text', e.target.value)}
          placeholder="Nombre, cargo..."
          prefix={<SearchOutlined />}
          style={{ marginTop: 4 }}
          size="small"
          allowClear
        />
      </div>

      {/* Active filters summary */}
      {(filters.convenios.length > 0 || filters.months.length < 12 || filters.contract_types.length < 3 || filters.search_text) && (
        <>
          <Divider style={{ margin: '8px 0' }} />
          <Typography.Text type="secondary" style={{ fontSize: 11 }}>
            Filtros activos: {[
              filters.months.length < 12 ? `${filters.months.length} meses` : null,
              filters.contract_types.length < 3 ? filters.contract_types.join(', ') : null,
              filters.convenios.length > 0 ? `${filters.convenios.length} convenios` : null,
              filters.search_text ? `"${filters.search_text}"` : null,
            ].filter(Boolean).join(' | ')}
          </Typography.Text>
        </>
      )}
    </div>
  );
}
