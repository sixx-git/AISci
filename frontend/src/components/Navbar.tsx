
import { Link, useLocation } from 'react-router-dom';
import { Home, BookOpen, ClipboardList } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ApiManagementPanel } from '@/components/ApiManagementPanel';

export function Navbar() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: '首页', icon: Home },
    { path: '/documents', label: '文献', icon: BookOpen },
    { path: '/reports', label: '报告', icon: ClipboardList },
  ];

  return (
    <nav className="bg-dark-800 border-b border-dark-700 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-4">
          <Link to="/" className="flex items-center gap-3 shrink-0">
            <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-xl flex items-center justify-center shadow-lg">
              <Home className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-primary-400 to-primary-600 bg-clip-text text-transparent">
                AI Scientist
              </h1>
              <p className="text-xs text-gray-500 -mt-1">智能科研助手</p>
            </div>
          </Link>

          <div className="flex items-center gap-1 min-w-0">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border border-transparent',
                    isActive
                      ? 'bg-primary-600/20 text-primary-400 border-primary-600/30'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-dark-700 hover:border-gray-600',
                  )}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className="hidden sm:inline">{item.label}</span>
                </Link>
              );
            })}
          </div>

          <div className="shrink-0">
            <ApiManagementPanel />
          </div>
        </div>
      </div>
    </nav>
  );
}
