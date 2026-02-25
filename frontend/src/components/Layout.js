import { createContext, useContext, useState, useCallback } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Upload, Users, Loader2, LayoutDashboard, Table2,
  FileWarning, Download, ChevronRight, Menu, X
} from "lucide-react";

// Session Context
export const SessionContext = createContext(null);
export const useSession = () => useContext(SessionContext);

const NAV_ITEMS = [
  { path: '/upload', label: 'Upload', icon: Upload, step: 1 },
  { path: '/identity', label: 'Identity Review', icon: Users, step: 2 },
  { path: '/processing', label: 'Processing', icon: Loader2, step: 3 },
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, step: 4 },
  { path: '/accounts', label: 'Accounts', icon: Table2, step: 5 },
  { path: '/exclusions', label: 'Exclusions', icon: FileWarning, step: 6 },
  { path: '/export', label: 'Export', icon: Download, step: 7 },
];

const STATUS_ORDER = { 'created': 1, 'validated': 2, 'identity_review': 2, 'processing': 3, 'completed': 7, 'error': 7 };

export default function Layout({ children, sessionId, sessionStatus }) {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const currentStep = STATUS_ORDER[sessionStatus] || 0;

  return (
    <div className="flex h-screen overflow-hidden bg-white" data-testid="app-layout">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/20 z-30 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={cn(
        "fixed inset-y-0 left-0 z-40 w-60 bg-slate-950 text-white flex flex-col transition-transform duration-200 lg:static lg:translate-x-0",
        sidebarOpen ? "translate-x-0" : "-translate-x-full"
      )} data-testid="sidebar">
        <div className="flex items-center gap-2 px-5 py-5 border-b border-slate-800">
          <div className="w-7 h-7 rounded bg-emerald-500 flex items-center justify-center">
            <span className="font-heading font-bold text-xs text-white">R</span>
          </div>
          <span className="font-heading font-bold text-base tracking-tight">RevStrux</span>
          <span className="text-[10px] text-slate-400 ml-auto">v1.1</span>
        </div>

        <ScrollArea className="flex-1 py-3">
          <nav className="px-3 space-y-0.5">
            {NAV_ITEMS.map((item) => {
              const active = location.pathname === item.path || (item.path === '/accounts' && location.pathname.startsWith('/accounts/'));
              const enabled = item.step <= currentStep || sessionStatus === 'completed';
              const Icon = item.icon;
              return (
                <Link
                  key={item.path}
                  to={enabled ? item.path : '#'}
                  data-testid={`nav-${item.label.toLowerCase().replace(/\s/g, '-')}`}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                    active ? "bg-slate-800 text-white" : "text-slate-400 hover:text-slate-200 hover:bg-slate-900",
                    !enabled && "opacity-40 pointer-events-none"
                  )}
                  onClick={() => setSidebarOpen(false)}
                >
                  <Icon size={16} />
                  {item.label}
                  {active && <ChevronRight size={14} className="ml-auto" />}
                </Link>
              );
            })}
          </nav>
        </ScrollArea>

        <div className="px-5 py-4 border-t border-slate-800">
          <p className="text-[10px] text-slate-500 leading-relaxed">
            All calculations are deterministic and rule-based. No AI or ML is used.
          </p>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-14 border-b border-slate-200 flex items-center px-4 lg:px-6 shrink-0 bg-white" data-testid="header">
          <Button variant="ghost" size="sm" className="lg:hidden mr-2" onClick={() => setSidebarOpen(true)} data-testid="menu-toggle">
            <Menu size={18} />
          </Button>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-slate-400">
              {sessionId ? `Session: ${sessionId}` : 'No active session'}
            </span>
            {sessionStatus && (
              <span className={cn(
                "text-[10px] font-medium px-2 py-0.5 rounded-full uppercase tracking-wider",
                sessionStatus === 'completed' ? 'bg-emerald-50 text-emerald-700' :
                sessionStatus === 'error' ? 'bg-red-50 text-red-700' :
                sessionStatus === 'processing' ? 'bg-blue-50 text-blue-700' :
                'bg-slate-100 text-slate-600'
              )} data-testid="session-status-badge">
                {sessionStatus}
              </span>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
