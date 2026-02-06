import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { Card } from 'antd';
import { useFilterStore } from '../../stores/filterStore';
import type { BreakdownRow } from '../../types';

interface Props {
  data: BreakdownRow[];
  title: string;
  chartType: 'pie' | 'bar';
  filterKey: 'convenio' | 'contract_type';
}

const COLORS = [
  '#1677ff', '#52c41a', '#faad14', '#f5222d', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#a0d911', '#2f54eb',
  '#597ef7', '#36cfc9', '#f759ab', '#ffc53d',
];

export default function BreakdownChart({ data, title, chartType, filterKey }: Props) {
  const applyChartFilter = useFilterStore((s) => s.applyChartFilter);

  let option: EChartsOption;

  if (chartType === 'pie') {
    option = {
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          const formatted = new Intl.NumberFormat('es-CL', {
            style: 'currency', currency: 'CLP', maximumFractionDigits: 0,
          }).format(params.value);
          return `${params.name}<br/>${formatted} (${params.percent}%)`;
        },
      },
      legend: {
        type: 'scroll',
        orient: 'vertical',
        right: 10,
        top: 20,
        bottom: 20,
        textStyle: { fontSize: 10 },
      },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 12, fontWeight: 'bold' },
        },
        data: data.map((d, i) => ({
          name: d.group_key,
          value: d.total,
          itemStyle: { color: COLORS[i % COLORS.length] },
        })),
      }],
    };
  } else {
    option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          if (!Array.isArray(params)) return '';
          const p = params[0];
          const formatted = new Intl.NumberFormat('es-CL', {
            style: 'currency', currency: 'CLP', maximumFractionDigits: 0,
          }).format(p.value);
          const row = data[p.dataIndex];
          return `<strong>${p.name}</strong><br/>${formatted}<br/>${row?.pct ?? 0}%`;
        },
      },
      grid: { left: 120, right: 40, top: 10, bottom: 30 },
      xAxis: {
        type: 'value',
        axisLabel: {
          fontSize: 10,
          formatter: (v: number) => {
            if (v >= 1e6) return `${(v / 1e6).toFixed(0)}M`;
            if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
            return String(v);
          },
        },
      },
      yAxis: {
        type: 'category',
        data: data.map(d => d.group_key),
        axisLabel: { fontSize: 10, width: 100, overflow: 'truncate' },
        inverse: true,
      },
      series: [{
        type: 'bar',
        data: data.map((d, i) => ({
          value: d.total,
          itemStyle: { color: COLORS[i % COLORS.length] },
        })),
        label: {
          show: true,
          position: 'right',
          fontSize: 10,
          formatter: (p: any) => `${data[p.dataIndex]?.pct ?? 0}%`,
        },
      }],
    };
  }

  const onEvents = {
    click: (params: any) => {
      const key = params.name || (data[params.dataIndex]?.group_key);
      if (key) {
        applyChartFilter(filterKey, key);
      }
    },
  };

  return (
    <Card size="small" title={title} bodyStyle={{ padding: '8px' }}>
      <ReactECharts
        option={option}
        style={{ height: chartType === 'bar' ? Math.max(200, data.length * 32 + 60) : 300 }}
        onEvents={onEvents}
        notMerge
      />
    </Card>
  );
}
