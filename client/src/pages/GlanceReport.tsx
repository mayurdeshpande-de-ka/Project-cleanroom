import { useEffect, useState } from 'react';
import axios from 'axios';
import { Calendar, Filter, ChevronDown, ChevronUp, Database, Loader2 } from 'lucide-react';

interface GlanceWeekData {
  week_label?: string;
  start_date?: string;
  end_date?: string;
  records_pushed: number;
  keys: Array<{
    state: string;
    pc_name: string;
    el_type: string;
    year: number;
    count?: number;
  }>;
  // It might be generic so we accept any structure
  [key: string]: any; 
}

export default function GlanceReport() {
  const [data, setData] = useState<GlanceWeekData[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedWeeks, setExpandedWeeks] = useState<Set<number>>(new Set());

  const [monthFilter, setMonthFilter] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [elTypeFilter, setElTypeFilter] = useState('');

  useEffect(() => {
    const fetchReport = async () => {
      setLoading(true);
      try {
        const params = {
          ...(monthFilter && { month: monthFilter }),
          ...(stateFilter && { state: stateFilter }),
          ...(elTypeFilter && { el_type: elTypeFilter })
        };
        const response = await axios.get('/api/glance_report', { params });
        
        // Handle varying response formats safely
        const weeks = response.data.all_weeks || (Array.isArray(response.data) ? response.data : []);
        setData(weeks);
        
        // Auto-expand the first week
        if (weeks.length > 0) {
          setExpandedWeeks(new Set([0]));
        }
      } catch (error) {
        console.error('Failed to fetch glance report:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [monthFilter, stateFilter, elTypeFilter]);

  const toggleWeek = (index: number) => {
    setExpandedWeeks(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Glance Report</h1>
          <p className="text-gray-500 mt-1">Weekly analysis of Form 20 DB pushes.</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-100 flex flex-wrap gap-4 items-center">
        <div className="flex items-center text-sm font-medium text-gray-700 mr-2">
          <Filter className="w-4 h-4 mr-2 text-gray-500" />
          Filter Report
        </div>
        
        <select 
          className="border border-gray-300 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none min-w-[150px] bg-gray-50/50"
          value={monthFilter}
          onChange={(e) => setMonthFilter(e.target.value)}
        >
          <option value="">All Months</option>
          <option value="1">January</option>
          <option value="2">February</option>
          <option value="3">March</option>
          <option value="4">April</option>
          <option value="5">May</option>
          <option value="6">June</option>
        </select>

        <select 
          className="border border-gray-300 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none min-w-[150px] bg-gray-50/50"
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
        >
          <option value="">All States</option>
          <option value="Uttar Pradesh">Uttar Pradesh</option>
          <option value="Maharashtra">Maharashtra</option>
          <option value="Bihar">Bihar</option>
        </select>

        <select 
          className="border border-gray-300 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none min-w-[150px] bg-gray-50/50"
          value={elTypeFilter}
          onChange={(e) => setElTypeFilter(e.target.value)}
        >
          <option value="">All Election Types</option>
          <option value="AE">Assembly (AE)</option>
          <option value="GE">General (GE)</option>
        </select>
      </div>

      {/* Content */}
      {loading ? (
        <div className="h-64 flex flex-col items-center justify-center bg-white rounded-xl shadow-sm border border-gray-100">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600 mb-4" />
          <p className="text-gray-500 font-medium">Generating Report...</p>
        </div>
      ) : data.length === 0 ? (
        <div className="h-64 flex flex-col items-center justify-center bg-white rounded-xl shadow-sm border border-gray-100">
          <Calendar className="w-12 h-12 text-gray-300 mb-4" />
          <p className="text-gray-600 font-medium text-lg">No data available</p>
          <p className="text-gray-400 mt-1">Adjust the filters to see weekly reports.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.map((week, index) => {
            const isExpanded = expandedWeeks.has(index);
            const weekLabel = week.week_label || `Week ${index + 1}`;
            const totalPushed = week.records_pushed || (week.keys ? week.keys.length : 0);
            
            return (
              <div key={index} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden transition-all duration-200">
                {/* Header / Toggle */}
                <button 
                  onClick={() => toggleWeek(index)}
                  className="w-full px-6 py-4 flex items-center justify-between bg-gray-50/50 hover:bg-gray-50 transition-colors focus:outline-none"
                >
                  <div className="flex items-center space-x-4">
                    <div className="p-2 bg-blue-100 text-blue-700 rounded-lg">
                      <Calendar className="w-5 h-5" />
                    </div>
                    <div className="text-left">
                      <h3 className="font-semibold text-gray-900">{weekLabel}</h3>
                      {week.start_date && week.end_date && (
                        <p className="text-sm text-gray-500">{week.start_date} - {week.end_date}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center space-x-6">
                    <div className="flex items-center text-sm font-medium text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full">
                      <Database className="w-4 h-4 mr-2" />
                      {totalPushed} Pushed
                    </div>
                    {isExpanded ? (
                      <ChevronUp className="w-5 h-5 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-gray-400" />
                    )}
                  </div>
                </button>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="px-6 py-4 border-t border-gray-100">
                    <h4 className="text-sm font-semibold text-gray-800 mb-4 uppercase tracking-wider">Pushed Keys Detail</h4>
                    {week.keys && week.keys.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {week.keys.map((keyInfo, kIdx) => (
                          <div key={kIdx} className="p-4 border border-gray-100 rounded-lg bg-gray-50 flex flex-col">
                            <div className="flex justify-between items-start mb-2">
                              <span className="font-medium text-gray-900">{keyInfo.state}</span>
                              <span className="text-xs font-bold bg-gray-200 text-gray-700 px-2 py-0.5 rounded">
                                {keyInfo.el_type} {keyInfo.year}
                              </span>
                            </div>
                            <div className="text-sm text-gray-600 mt-auto pt-2 border-t border-gray-200/60 flex items-center justify-between">
                              <span>PC: <span className="font-medium text-gray-800">{keyInfo.pc_name || 'N/A'}</span></span>
                              {keyInfo.count !== undefined && (
                                <span className="text-blue-600 font-semibold">{keyInfo.count} records</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="py-8 text-center text-gray-500 bg-gray-50 rounded-lg border border-dashed border-gray-200">
                        No detailed keys available for this week.
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
