import { Link, useLocation } from 'react-router-dom';
import { Home, BookOpen, ClipboardList } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DeveloperMenu } from '@/components/DeveloperMenu';

export function Navbar() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: '首页', icon: Home },
    { path: '/documents', label: '文献', icon: BookOpen },
    { path: '/reports', label: '报告', icon: ClipboardList },
  ];

  return (
    <nav className="bg-bp-panel border-b border-bp-border sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-4">
          <Link to="/" className="flex items-center gap-3 shrink-0">
            <div className="w-10 h-10 bg-bp-cyan rounded-bp flex items-center justify-center shadow-bp-glow">
              <Home className="w-6 h-6 text-bp-base" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-bp-cyan font-mono">[AISci]</h1>
              <p className="text-xs text-bp-muted -mt-1">智能科研助手</p>
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
                    'flex items-center gap-2 px-3 py-2 rounded-bp text-sm font-medium border',
                    isActive
                      ? 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/30'
                      : 'border-transparent text-bp-muted hover:text-bp-text hover:bg-bp-surface hover-accent-bottom',
                  )}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className="hidden sm:inline">{item.label}</span>
                </Link>
              );
            })}
          </div>

          <div className="shrink-0">
            <DeveloperMenu />
          </div>
        </div>
      </div>
    </nav>
  );
}
