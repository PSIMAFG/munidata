import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { Card } from 'antd';
import { useFilterStore } from '../../stores/filterStore';
import type { TimeseriesRow } from '../../types';
import { MONTH_NAMES } from '../../types';

interface Props {
  data: TimeseriesRow[];
  title: string;
  groupMode: 'contract_type' | 'convenio';
}

const COLORS = [
  '#1677ff', '#52c41a', '#faad14', '#f5222d', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#a0d911', '#2f54eb',
];

export default function TimeseriesChart({ data, title, groupMode }: Props) {
  const applyChartFilter = useFilterStore((s) => s.applyChartFilter);

  const months = [...new Set(data.map(d => d.month))].sort((a, b) => a - b);
  const groups = [...new Set(data.map(d => d.group_key))];

  const series = groups.map((g, idx) => ({
    name: g,
    type: 'bar' as const,
    stack: 'total',
    data: months.map(m => {
      const row = data.find(d => d.month === m && d.group_key === g);
      return row ? row.total : 0;
    }),
    itemStyle: { color: COLORS[idx % COLORS.length] },
    emphasis: { focus: 'series' as const },
  }));

  // Total line overlay
  const totalSeries = {
    name: 'Total',
    type: 'line' as const,
    data: months.map(m => data.filter(d => d.month === m).reduce((s, d) => s + d.total, 0)),
    itemStyle: { color: '#333' },
    lineStyle: { width: 2, type: 'dashed' as const },
    symbol: 'circle',
    symbolSize: 6,
  };

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        if (!Array.isArray(params)) return '';
        let html = `<strong>${params[0]?.name}</strong><br/>`;
        for (const p of params) {
          if (p.value > 0) {
            const formatted = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(p.value);
            html += `${p.marker} ${p.seriesName}: ${formatted}<br/>`;
          }
        }
        return html;
      },
    },
    legend: {
      type: 'scroll',
      bottom: 0,
      textStyle: { fontSize: 10 },
    },
    grid: { left: 80, right: 20, top: 20, bottom: 60 },
    xAxis: {
      type: 'category',
      data: months.map(m => MONTH_NAMES[m]?.substring(0, 3) || String(m)),
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        fontSize: 10,
        formatter: (v: number) => {
          if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
          if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
          if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
          return String(v);
        },
      },
    },
    series: [...series, totalSeries],
  };

  const onEvents = {
    click: (params: any) => {
      if (params.componentType === 'series') {
        const monthIdx = params.dataIndex;
        const month = months[monthIdx];
        if (month) {
          applyChartFilter('month', String(month));
        }
        if (groupMode === 'convenio' && params.seriesName !== 'Total') {
          applyChartFilter('convenio', params.seriesName);
        }
      }
    },
  };

  return (
    <Card size="small" title={title} bodyStyle={{ padding: '8px' }}>
      <ReactECharts
        option={option}
        style={{ height: 300 }}
        onEvents={onEvents}
        notMerge
      />
    </Card>
  );
}
