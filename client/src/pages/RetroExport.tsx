import React, { useState } from 'react';
import axios from 'axios';
import { Download, AlertCircle, CheckCircle2, Loader2, FileDown } from 'lucide-react';

export default function RetroExport() {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  const [stateFilter, setStateFilter] = useState('');
  const [elType, setElType] = useState('');
  const [year, setYear] = useState('');

  const handleExport = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      // Assuming it responds with a blob or JSON success message
      // We will send a POST request
      const payload = {
        state: stateFilter || undefined,
        el_type: elType || undefined,
        year: year ? parseInt(year) : undefined
      };
      
      const response = await axios.post('/retro_export', payload, {
        // If the endpoint returns a file:
        // responseType: 'blob'
      });
      
      // If returning a file blob
      if (response.data instanceof Blob) {
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `retro_export_${new Date().getTime()}.xlsx`);
        document.body.appendChild(link);
        link.click();
        link.parentNode?.removeChild(link);
        setSuccess('Export downloaded successfully!');
      } else {
        setSuccess(response.data.message || 'Export triggered successfully! Check your downloads or email.');
      }
    } catch (err: any) {
      console.error('Export failed:', err);
      setError(err.response?.data?.message || 'Failed to trigger export. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 pt-4">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-100 mb-4">
          <FileDown className="w-8 h-8 text-blue-600" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Retro Export</h1>
        <p className="text-gray-500 mt-2 text-lg max-w-lg mx-auto">
          Generate historical backlog reports by applying specific filters and export them for offline analysis.
        </p>
      </div>

      <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100">
        <form onSubmit={handleExport} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">State</label>
              <select 
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow bg-gray-50 hover:bg-white"
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
              >
                <option value="">All States</option>
                <option value="Uttar Pradesh">Uttar Pradesh</option>
                <option value="Maharashtra">Maharashtra</option>
                <option value="Bihar">Bihar</option>
                <option value="West Bengal">West Bengal</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">Election Type</label>
              <select 
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow bg-gray-50 hover:bg-white"
                value={elType}
                onChange={(e) => setElType(e.target.value)}
              >
                <option value="">All Election Types</option>
                <option value="AE">Assembly (AE)</option>
                <option value="GE">General (GE)</option>
              </select>
            </div>

            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium text-gray-700">Year</label>
              <input 
                type="number"
                placeholder="e.g. 2024"
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow bg-gray-50 hover:bg-white"
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="p-4 bg-red-50 text-red-700 rounded-xl flex items-center border border-red-100">
              <AlertCircle className="w-5 h-5 mr-3 flex-shrink-0" />
              <p className="text-sm font-medium">{error}</p>
            </div>
          )}

          {success && (
            <div className="p-4 bg-emerald-50 text-emerald-800 rounded-xl flex items-center border border-emerald-100">
              <CheckCircle2 className="w-5 h-5 mr-3 flex-shrink-0" />
              <p className="text-sm font-medium">{success}</p>
            </div>
          )}

          <div className="pt-4 border-t border-gray-100">
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-xl transition-colors disabled:opacity-70 disabled:cursor-not-allowed shadow-sm"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Processing Export...</span>
                </>
              ) : (
                <>
                  <Download className="w-5 h-5" />
                  <span>Generate Export</span>
                </>
              )}
            </button>
            <p className="text-xs text-center text-gray-500 mt-4">
              Exports might take a few moments depending on the data size. The file will download automatically once ready.
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
