import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, List, FileText, ArrowDownToLine } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Listing from './pages/Listing';
import GlanceReport from './pages/GlanceReport';
import RetroExport from './pages/RetroExport';

function Sidebar() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/listing', label: 'Listing', icon: List },
    { path: '/glance', label: 'Glance Report', icon: FileText },
    { path: '/retro', label: 'Retro Export', icon: ArrowDownToLine },
  ];

  return (
    <div className="w-64 bg-white border-r border-gray-200 h-screen fixed top-0 left-0 flex flex-col z-10 shadow-sm">
      <div className="h-16 flex items-center px-6 border-b border-gray-100">
        <h1 className="text-xl font-bold text-gray-900">Form 20 Tracker</h1>
      </div>
      <nav className="flex-1 px-4 py-6 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          const Icon = item.icon;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center px-4 py-3 rounded-lg transition-colors text-sm ${
                isActive 
                  ? 'bg-blue-50 text-blue-700 font-semibold' 
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900 font-medium'
              }`}
            >
              <Icon className="w-5 h-5 mr-3" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50 font-sans">
        <Sidebar />
        <main className="ml-64 p-8 min-h-screen">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/listing" element={<Listing />} />
            <Route path="/glance" element={<GlanceReport />} />
            <Route path="/retro" element={<RetroExport />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
