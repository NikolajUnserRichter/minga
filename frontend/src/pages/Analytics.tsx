import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ComposedChart, Line,
} from 'recharts';
import { analyticsApi } from '../services/api';
import { RevenueStats, YieldStats } from '../types';
import { Euro, TrendingUp, Sprout } from 'lucide-react';
import { PageHeader } from '../components/common/Layout';
import { StatCard } from '../components/domain/StatCard';
import { SkeletonStatCard, SkeletonChart } from '../components/ui/Skeleton';

export default function Analytics() {
  const { data: revenueData = [], isLoading: revLoading } = useQuery<RevenueStats[]>({
    queryKey: ['analytics', 'revenue'],
    queryFn: () => analyticsApi.getRevenue(),
  });

  const { data: yieldData = [], isLoading: yieldLoading } = useQuery<YieldStats[]>({
    queryKey: ['analytics', 'yield'],
    queryFn: () => analyticsApi.getYield(),
  });

  const isLoading = revLoading || yieldLoading;

  const processedRevenue = useMemo(() => {
    const map = new Map<string, Record<string, number | string>>();
    revenueData.forEach((item) => {
      if (!map.has(item.month)) {
        map.set(item.month, { month: item.month, GASTRO: 0, HANDEL: 0, PRIVAT: 0 });
      }
      const entry = map.get(item.month)!;
      entry[item.customer_type] = Number(item.revenue);
    });
    return Array.from(map.values()).sort((a, b) =>
      String(a.month).localeCompare(String(b.month)),
    );
  }, [revenueData]);

  const totalRevenue = revenueData.reduce((acc, curr) => acc + Number(curr.revenue), 0);
  const avgEfficiency =
    yieldData.length > 0
      ? yieldData.reduce((acc, curr) => acc + curr.efficiency_percent, 0) / yieldData.length
      : 0;

  return (
    <div className="space-y-6">
      <PageHeader title="Auswertungen" subtitle="Umsatz- und Ertragsübersicht" />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {isLoading ? (
          <>
            <SkeletonStatCard />
            <SkeletonStatCard />
            <SkeletonStatCard />
          </>
        ) : (
          <>
            <StatCard
              title="Umsatz (L12M)"
              value={totalRevenue.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' })}
              icon={<Euro className="w-5 h-5" />}
              variant="info"
            />
            <StatCard
              title="Yield-Effizienz Ø"
              value={`${avgEfficiency.toFixed(1)}%`}
              icon={<Sprout className="w-5 h-5" />}
              variant="success"
            />
            <StatCard
              title="Sorten im Anbau"
              value={yieldData.length}
              icon={<TrendingUp className="w-5 h-5" />}
              variant="primary"
            />
          </>
        )}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {isLoading ? (
          <>
            <SkeletonChart />
            <SkeletonChart />
          </>
        ) : (
          <>
            {/* Revenue Chart */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Umsatzentwicklung nach Kundentyp
              </h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={processedRevenue}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                    <XAxis dataKey="month" className="text-xs" />
                    <YAxis className="text-xs" />
                    <Tooltip
                      formatter={(value) => Number(value).toFixed(2) + ' €'}
                      contentStyle={{
                        backgroundColor: 'var(--color-card-bg, #fff)',
                        borderColor: 'var(--color-border, #e5e7eb)',
                        borderRadius: '0.5rem',
                      }}
                    />
                    <Legend />
                    <Bar dataKey="GASTRO" stackId="a" fill="var(--color-info, #3b82f6)" name="Gastro" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="HANDEL" stackId="a" fill="var(--color-primary, #10b981)" name="Handel" />
                    <Bar dataKey="PRIVAT" stackId="a" fill="var(--color-warning, #f59e0b)" name="Privat" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Yield Efficiency Chart */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Ertragseffizienz (Ist vs Soll)
              </h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={yieldData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                    <XAxis type="number" unit="%" domain={[0, 'auto']} className="text-xs" />
                    <YAxis dataKey="variety" type="category" width={100} className="text-xs" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--color-card-bg, #fff)',
                        borderColor: 'var(--color-border, #e5e7eb)',
                        borderRadius: '0.5rem',
                      }}
                    />
                    <Legend />
                    <Bar dataKey="efficiency_percent" barSize={20} fill="var(--color-primary, #8884d8)" name="Effizienz %" radius={[0, 4, 4, 0]} />
                    <Line dataKey="efficiency_percent" stroke="var(--color-warning, #ff7300)" name="Trend" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
