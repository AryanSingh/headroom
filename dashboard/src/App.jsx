import { useDeferredValue, useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  Home,
  Moon,
  PanelLeftOpen,
  Search,
  Shield,
  Sun,
  TerminalSquare,
  Zap,
} from 'lucide-react';
import Overview from './pages/Overview';
import Firewall from './pages/Firewall';
import Memory from './pages/Memory';
import Playground from './pages/Playground';
import Capabilities from './pages/Capabilities';
import { DashboardDataProvider } from './lib/dashboard-context';
import { useDashboardData } from './lib/use-dashboard-data';
import { ThemeProvider, useTheme } from './lib/theme-context';

const navItems = [
  { path: '/', label: 'Dashboard', icon: Home },
  { path: '/capabilities', label: 'Capabilities', icon: Zap },
  { path: '/firewall', label: 'Security', icon: Shield },
  { path: '/memory', label: 'Memory', icon: BarChart3 },
  { path: '/playground', label: 'Playground', icon: TerminalSquare },
];

/* ─── Sidebar ─────────────────────────────────────────────────── */

function Sidebar({ open, onClose }) {
  return (
    <>
      <div
        className={`sidebar-overlay ${open ? 'visible' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside className={`sidebar-shell ${open ? 'open' : ''}`}>
        <div className="brand-lockup">
          <div className="brand-mark">
            <Activity size={16} />
          </div>
          <h1>Cutctx</h1>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">Navigation</div>
          <nav className="nav-stack">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === '/'}
                  className={({ isActive }) => `nav-card ${isActive ? 'active' : ''}`}
                  onClick={onClose}
                >
                  <div className="nav-card-icon">
                    <Icon size={16} />
                  </div>
                  <div>
                    <div className="nav-card-title">{item.label}</div>
                  </div>
                </NavLink>
              );
            })}
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-label">Surfaces</div>
          <div className="promo-card">
            <div className="promo-row">
              <Shield size={12} />
              Proxy, wrap, library, MCP
            </div>
            <div className="promo-row">
              <Zap size={12} />
              Memory, CCR, firewall, savings
            </div>
          </div>
          <div className="sidebar-footer-label">v0.1.0</div>
        </div>
      </aside>
    </>
  );
}

/* ─── Topbar ──────────────────────────────────────────────────── */

function Topbar({
  searchQuery,
  setSearchQuery,
  searchInputRef,
  onToggleSidebar,
}) {
  const location = useLocation();
  const { health } = useDashboardData();
  const { theme, toggleTheme } = useTheme();

  const currentNav = useMemo(
    () => navItems.find((item) => item.path === location.pathname) || navItems[0],
    [location.pathname],
  );

  return (
    <header className="topbar-shell">
      <div className="topbar-left">
        <button
          className="sidebar-toggle-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
          type="button"
        >
          <PanelLeftOpen size={18} />
        </button>

        <div className="topbar-title-group">
          <div className="topbar-title-row">
            <h2>{currentNav.label}</h2>
            <span className="status-pill">
              <span className={`status-dot ${health?.ready ? 'ok' : ''}`} />
              {health?.status || 'connecting'}
            </span>
          </div>
        </div>
      </div>

      <div className="topbar-tools">
        <label className="search-shell" aria-label="Search dashboard">
          <Search size={14} />
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search"
            aria-label="Search"
          />
          <span className="search-shortcut">/</span>
        </label>

        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          type="button"
        >
          <span className="icon-sun">
            <Sun size={16} />
          </span>
          <span className="icon-moon">
            <Moon size={16} />
          </span>
        </button>
      </div>
    </header>
  );
}

/* ─── App Frame ───────────────────────────────────────────────── */

function AppFrame() {
  const searchInputRef = useRef(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1024px)');
    const handler = (e) => {
      setIsMobile(e.matches);
      if (e.matches) setSidebarOpen(false);
      else setSidebarOpen(true);
    };
    handler(mq);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev);
  }, []);

  const closeSidebar = useCallback(() => {
    if (isMobile) setSidebarOpen(false);
  }, [isMobile]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
        if (event.key === 'Escape') {
          event.target.blur();
        }
        return;
      }
      if (event.key === '/') {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className={`app-shell ${!sidebarOpen && !isMobile ? 'sidebar-collapsed' : ''}`}>
      <Sidebar open={sidebarOpen} onClose={closeSidebar} />
      <div className="content-shell">
        <Topbar
          searchInputRef={searchInputRef}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          onToggleSidebar={toggleSidebar}
        />
        <main className="page-shell">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/capabilities" element={<Capabilities />} />
            <Route path="/firewall" element={<Firewall />} />
            <Route path="/memory" element={<Memory />} />
            <Route path="/playground" element={<Playground />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter basename={window.location.pathname.startsWith('/admin') ? '/admin' : '/dashboard'}>
      <ThemeProvider>
        <DashboardDataProvider>
          <AppFrame />
        </DashboardDataProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
