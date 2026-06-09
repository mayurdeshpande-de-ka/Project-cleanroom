import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Search, ChevronLeft, ChevronRight, CheckCircle2, AlertTriangle, Clock, Filter, FileText } from 'lucide-react';
import { useDebounce } from '../hooks/useDebounce'; // We will create this

interface RecordData {
  id?: string;
  state: string;
  pc_name: string | null;
  ac_name: string | null;
  el_type: string;
  year: number;
  status: string;
  sir_status: string;
}

interface ApiResponse {
  items: RecordData[];
  total: number;
  page: number;
  size: number;
}

export default function Listing() {
  const [data, setData] = useState<ApiResponse>({ items: [], total: 0, page: 1, size: 20 });
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [page, setPage] = useState(1);
  const [size] = useState(20);
  const [search, setSearch] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [elTypeFilter, setElTypeFilter] = useState('');
  
  const debouncedSearch = useDebounce(search, 500);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page,
        size,
        ...(debouncedSearch && { search: debouncedSearch }),
        ...(stateFilter && { state: stateFilter }),
        ...(elTypeFilter && { el_type: elTypeFilter })
      };
      
      const response = await axios.get('/api/records', { params });
      
      // Handle the case where the API returns a direct array or the expected object
      if (Array.isArray(response.data)) {
        setData({ items: response.data, total: response.data.length, page, size });
      } else {
        setData({
          items: response.data.items || [],
          total: response.data.total || 0,
          page: response.data.page || 1,
          size: response.data.size || 20
        });
      }
    } catch (error) {
      console.error('Failed to fetch records:', error);
    } finally {
      setLoading(false);
    }
  }, [page, size, debouncedSearch, stateFilter, elTypeFilter]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  const totalPages = Math.max(1, Math.ceil(data.total / size));

  const getStatusBadge = (status: string) => {
    if (status === 'Received') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
          <CheckCircle2 className="w-3 h-3 mr-1" />
          Received
        </span>
      );
    }
    if (status === 'Not Received' || status === 'Pending') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-800">
          <AlertTriangle className="w-3 h-3 mr-1" />
          Missing
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
        <Clock className="w-3 h-3 mr-1" />
        {status || 'WIP'}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Form 20 Listing</h1>
          <p className="text-gray-500 mt-1">Search, filter, and review individual form statuses.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search PC/AC..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none w-full sm:w-64 transition-shadow text-sm"
            />
          </div>
        </div>
      </div>

      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-wrap gap-4 items-center">
        <div className="flex items-center text-sm font-medium text-gray-600 mr-2">
          <Filter className="w-4 h-4 mr-2" />
          Filters
        </div>
        
        <select 
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
          value={stateFilter}
          onChange={(e) => { setStateFilter(e.target.value); setPage(1); }}
        >
          <option value="">All States</option>
          <option value="Uttar Pradesh">Uttar Pradesh</option>
          <option value="Maharashtra">Maharashtra</option>
          <option value="Bihar">Bihar</option>
          <option value="West Bengal">West Bengal</option>
          {/* Real implementation would dynamically generate this list from an API */}
        </select>

        <select 
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
          value={elTypeFilter}
          onChange={(e) => { setElTypeFilter(e.target.value); setPage(1); }}
        >
          <option value="">All Election Types</option>
          <option value="AE">Assembly (AE)</option>
          <option value="GE">General (GE)</option>
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden relative min-h-[400px]">
        {loading && (
          <div className="absolute inset-0 bg-white/50 backdrop-blur-sm z-10 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        )}
        
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="px-6 py-4 font-semibold">State / Year</th>
                <th className="px-6 py-4 font-semibold">Election Type</th>
                <th className="px-6 py-4 font-semibold">PC Name</th>
                <th className="px-6 py-4 font-semibold">AC Name</th>
                <th className="px-6 py-4 font-semibold">Status</th>
                <th className="px-6 py-4 font-semibold">SIR Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data.items.length > 0 ? (
                data.items.map((record, i) => (
                  <tr key={record.id || i} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-medium text-gray-900">{record.state}</div>
                      <div className="text-gray-500 text-xs mt-0.5">{record.year}</div>
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      <span className="inline-flex items-center px-2 py-1 rounded bg-gray-100 text-gray-700 text-xs font-medium">
                        {record.el_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-medium text-gray-800">{record.pc_name || '-'}</td>
                    <td className="px-6 py-4 text-gray-600">{record.ac_name || '-'}</td>
                    <td className="px-6 py-4">
                      {getStatusBadge(record.status)}
                    </td>
                    <td className="px-6 py-4">
                      {getStatusBadge(record.sir_status)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center">
                    <div className="flex flex-col items-center justify-center text-gray-400">
                      <FileText className="w-12 h-12 mb-3 text-gray-300" />
                      <p className="text-base font-medium text-gray-600">No records found</p>
                      <p className="text-sm">Try adjusting your search or filters.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between bg-gray-50">
          <div className="text-sm text-gray-500">
            Showing <span className="font-medium text-gray-900">{(page - 1) * size + 1}</span> to <span className="font-medium text-gray-900">{Math.min(page * size, data.total)}</span> of{' '}
            <span className="font-medium text-gray-900">{data.total}</span> records
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <div className="text-sm font-medium text-gray-700 px-2">
              Page {page} of {totalPages}
            </div>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages || totalPages === 0}
              className="p-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
