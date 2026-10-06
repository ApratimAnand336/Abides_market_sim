import { memo, useCallback, useEffect, useRef } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';
import './theme';

interface Props {
  option: EChartsOption;
  height: number;
  /** Charts sharing a group share zoom window and crosshair (one group per tab). */
  group?: string;
  onEvents?: Record<string, (params: any, chart: echarts.ECharts) => void>;
  ariaLabel: string;
  className?: string;
}

/** Thin wrapper: theme, group connection, double-click zoom reset. */
export const EChart = memo(function EChart({ option, height, group, onEvents, ariaLabel, className }: Props) {
  const ref = useRef<ReactEChartsCore>(null);

  const onReady = useCallback(
    (chart: echarts.ECharts) => {
      if (group) {
        chart.group = group;
        echarts.connect(group);
      }
      // double-click anywhere resets the shared time window
      chart.getZr().on('dblclick', () => resetZoom(chart));
    },
    [group],
  );

  useEffect(() => {
    // keep group membership if the group name changes
    const chart = ref.current?.getEchartsInstance();
    if (chart && group) {
      chart.group = group;
      echarts.connect(group);
    }
  }, [group]);

  return (
    <div role="img" aria-label={ariaLabel} className={className}>
      <ReactEChartsCore
        ref={ref}
        echarts={echarts}
        option={{ aria: { enabled: true, label: { description: ariaLabel } }, ...option }}
        theme="finverse"
        notMerge
        lazyUpdate
        style={{ height, width: '100%' }}
        onChartReady={onReady}
        onEvents={onEvents}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  );
});

export function resetZoom(chart: echarts.ECharts) {
  chart.dispatchAction({ type: 'dataZoom', start: 0, end: 100 });
}

/** Reset the zoom of every chart in a group (the "Reset zoom" button). */
export function resetGroupZoom(group: string) {
  const dom = document.querySelectorAll<HTMLElement>('[_echarts_instance_]');
  for (const el of dom) {
    const chart = echarts.getInstanceByDom(el);
    if (chart && chart.group === group) {
      resetZoom(chart);
      return; // connect() propagates to the rest of the group
    }
  }
}
