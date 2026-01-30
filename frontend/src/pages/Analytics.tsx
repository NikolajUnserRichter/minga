import React, { useState, useEffect } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    ComposedChart, Line
} from 'recharts';
import { analyticsApi } from '../services/api';
import { RevenueStats, YieldStats } from '../types';
import { Euro, TrendingUp, Sprout } from 'lucide-react';

const Analytics = () => {
    const [revenueData, setRevenueData] = useState<RevenueStats[]>([]);
    const [yieldData, setYieldData] = useState<YieldStats[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [rev, yld] = await Promise.all([
                    analyticsApi.getRevenue(),
                    analyticsApi.getYield()
                ]);
                setRevenueData(rev);
                setYieldData(yld);
            } catch (err) {
                console.error("Failed to load analytics", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    // Transform Revenue Data for Chart (Group by Month)
    const processedRevenue = React.useMemo(() => {
        const map = new Map();
        revenueData.forEach(item => {
            if (!map.has(item.month)) {
                map.set(item.month, { month: item.month, GASTRO: 0, HANDEL: 0, PRIVAT: 0 });
            }
            const entry = map.get(item.month);
            entry[item.customer_type] = Number(item.revenue);
        });
        return Array.from(map.values()).sort((a, b) => a.month.localeCompare(b.month));
    }, [revenueData]);

    // Calculate Totals
    const totalRevenue = revenueData.reduce((acc, curr) => acc + Number(curr.revenue), 0);
    const avgEfficiency = yieldData.length > 0
        ? yieldData.reduce((acc, curr) => acc + curr.efficiency_percent, 0) / yieldData.length
        : 0;

    if (loading) return <div className="p-8">Lade Analysen...</div>;

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold text-gray-800">Analytics Dashboard</h1>

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100 flex items-center space-x-4">
                    <div className="p-3 bg-blue-100 text-blue-600 rounded-full">
                        <Euro className="w-6 h-6" />
                    </div>
                    <div>
                        <p className="text-sm text-gray-500">Umsatz (L12M)</p>
                        <p className="text-2xl font-bold">{totalRevenue.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' })}</p>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100 flex items-center space-x-4">
                    <div className="p-3 bg-green-100 text-green-600 rounded-full">
                        <Sprout className="w-6 h-6" />
                    </div>
                    <div>
                        <p className="text-sm text-gray-500">Yield Effizienz Ø</p>
                        <p className="text-2xl font-bold">{avgEfficiency.toFixed(1)}%</p>
                    </div>
                </div>

                <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100 flex items-center space-x-4">
                    <div className="p-3 bg-purple-100 text-purple-600 rounded-full">
                        <TrendingUp className="w-6 h-6" />
                    </div>
                    <div>
                        <p className="text-sm text-gray-500">Sorten im Anbau</p>
                        <p className="text-2xl font-bold">{yieldData.length}</p>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Revenue Chart */}
                <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                    <h3 className="text-lg font-semibold mb-4">Umsatzentwicklung nach Kundentyp</h3>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={processedRevenue}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="month" />
                                <YAxis />
                                <Tooltip formatter={(value) => Number(value).toFixed(2) + ' €'} />
                                <Legend />
                                <Bar dataKey="GASTRO" stackId="a" fill="#3b82f6" name="Gastro" />
                                <Bar dataKey="HANDEL" stackId="a" fill="#10b981" name="Handel" />
                                <Bar dataKey="PRIVAT" stackId="a" fill="#f59e0b" name="Privat" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Yield Efficiency Chart */}
                <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                    <h3 className="text-lg font-semibold mb-4">Ertragseffizienz (Ist vs Soll)</h3>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <ComposedChart data={yieldData} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis type="number" unit="%" domain={[0, 'auto']} />
                                <YAxis dataKey="variety" type="category" width={100} />
                                <Tooltip />
                                <Legend />
                                <Bar dataKey="efficiency_percent" barSize={20} fill="#8884d8" name="Effizienz %" />
                                <Line dataKey="efficiency_percent" stroke="#ff7300" />
                            </ComposedChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Analytics;
