import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { 
  PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer, 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend 
} from 'recharts';
import { Loader2, AlertCircle, TrendingUp, Clock, CheckCircle2, FileText } from 'lucide-react';

interface StatsData {
  total: number;
  by_status: Record<string, number>;
  sir_by_status: Record<string, number>;
  wip_count: number;
  by_state: Array<{
    state: string;
    total: number;
    received: number;
    not_received: number;
  }>;
  by_type: Record<string, number>;
  bottlenecks: Array<{
    state: string;
    pc_name: string;
    not_received: number;
  }>;
}

const STATUS_COLORS = {
  'Received': '#10b981',
  'Not Received': '#ef4444',
  'WIP': '#f59e0b',
  'default': '#3b82f6'
};

export default function Dashboard() {
  const [data, setData] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await axios.get('/api/stats');
        setData(response.data);
      } catch (err) {
        console.error('Failed to fetch stats:', err);
        setError('Failed to load dashboard data. Please make sure the backend server is running.');
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="flex flex-col items-center text-gray-500 space-y-4">
          <Loader2 className="w-10 h-10 animate-spin text-blue-600" />
          <p className="font-medium">Loading insights...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 max-w-lg mx-auto mt-20 bg-red-50 border border-red-200 rounded-xl flex items-start space-x-4">
        <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="font-semibold text-red-800">Connection Error</h3>
          <p className="text-red-600 text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  // Prepare chart data
  const statusChartData = Object.entries(data.by_status || {}).map(([name, value]) => ({
    name,
    value
  }));

  const typeChartData = Object.entries(data.by_type || {}).map(([name, value]) => ({
    name,
    value
  }));

  const stateChartData = (data.by_state || []).slice(0, 10); // Top 10 states

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Overview Dashboard</h1>
        <p className="text-gray-500 mt-1">Real-time Form 20 collection statistics and bottlenecks.</p>
      </div>

      {/* Top Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard 
          title="Total Forms" 
          value={data.total} 
          icon={<FileText className="w-5 h-5 text-blue-600" />}
          bgColor="bg-blue-50"
        />
        <MetricCard 
          title="Forms Received" 
          value={data.by_status['Received'] || 0} 
          icon={<CheckCircle2 className="w-5 h-5 text-emerald-600" />}
          bgColor="bg-emerald-50"
        />
        <MetricCard 
          title="Work In Progress" 
          value={data.wip_count || 0} 
          icon={<Clock className="w-5 h-5 text-amber-600" />}
          bgColor="bg-amber-50"
        />
        <MetricCard 
          title="Missing Forms" 
          value={data.by_status['Not Received'] || 0} 
          icon={<AlertCircle className="w-5 h-5 text-rose-600" />}
          bgColor="bg-rose-50"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Status Distribution */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 col-span-1 lg:col-span-1">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Status Distribution</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={statusChartData}
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {statusChartData.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={STATUS_COLORS[entry.name as keyof typeof STATUS_COLORS] || STATUS_COLORS.default} 
                    />
                  ))}
                </Pie>
                <RechartsTooltip 
                  formatter={(value: any) => [`${value} Forms`, 'Count']}
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Legend verticalAlign="bottom" height={36} iconType="circle" />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* State Wise Collection */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 col-span-1 lg:col-span-2">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">State-wise Collection (Top 10)</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={stateChartData}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                <XAxis 
                  dataKey="state" 
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  dy={10}
                />
                <YAxis 
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                />
                <RechartsTooltip 
                  cursor={{ fill: '#f9fafb' }}
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px' }} />
                <Bar dataKey="received" name="Received" stackId="a" fill="#10b981" radius={[0, 0, 4, 4]} maxBarSize={40} />
                <Bar dataKey="not_received" name="Not Received" stackId="a" fill="#ef4444" radius={[4, 4, 0, 0]} maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Type Distribution */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Election Type</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={typeChartData}
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {typeChartData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={['#8b5cf6', '#ec4899', '#0ea5e9'][index % 3]} />
                  ))}
                </Pie>
                <RechartsTooltip 
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Legend verticalAlign="bottom" height={36} iconType="circle" />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bottlenecks */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-800 flex items-center">
              <TrendingUp className="w-5 h-5 mr-2 text-rose-500" />
              Top Bottlenecks
            </h2>
            <span className="text-sm font-medium text-gray-500 px-2 py-1 bg-gray-100 rounded-md">Missing Forms</span>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-500 uppercase bg-gray-50 rounded-lg">
                <tr>
                  <th className="px-4 py-3 rounded-l-lg font-semibold">State</th>
                  <th className="px-4 py-3 font-semibold">PC Name</th>
                  <th className="px-4 py-3 rounded-r-lg font-semibold text-right">Missing</th>
                </tr>
              </thead>
              <tbody>
                {(data.bottlenecks || []).slice(0, 5).map((row, i) => (
                  <tr key={i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900">{row.state}</td>
                    <td className="px-4 py-3 text-gray-600">{row.pc_name || '-'}</td>
                    <td className="px-4 py-3 text-right font-semibold text-rose-600">{row.not_received}</td>
                  </tr>
                ))}
                {(!data.bottlenecks || data.bottlenecks.length === 0) && (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-gray-500">
                      No bottlenecks identified. Great job!
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, icon, bgColor }: { title: string; value: number | string; icon: React.ReactNode; bgColor: string }) {
  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-center space-x-4">
      <div className={`p-4 rounded-xl ${bgColor}`}>
        {icon}
      </div>
      <div>
        <p className="text-sm font-medium text-gray-500">{title}</p>
        <h3 className="text-2xl font-bold text-gray-900 tracking-tight mt-0.5">{value}</h3>
      </div>
    </div>
  );
}
