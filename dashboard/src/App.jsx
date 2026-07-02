import { readStoredAdminKey, writeStoredAdminKey } from './lib/admin-auth';
import { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  BookOpen,
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
import Governance from './pages/Governance';
import Memory from './pages/Memory';
import Playground from './pages/Playground';
import Capabilities from './pages/Capabilities';
import Docs from './pages/Docs';
import Orchestrator from './pages/Orchestrator';
import { DashboardDataProvider } from './lib/dashboard-context';
import { useDashboardData } from './lib/use-dashboard-data';
import { ThemeProvider, useTheme } from './lib/theme-context';

/* ─── Error Boundary ──────────────────────────────────────────── */

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    if (import.meta.env.DEV) {
      console.error('ErrorBoundary caught an error', error, errorInfo);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 'var(--space-3xl)', color: 'var(--text-primary)', background: 'var(--surface-0)', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
          <h2 style={{ marginBottom: 'var(--space-md)' }}>Something went wrong.</h2>
          <pre style={{ background: 'var(--surface-2)', padding: 'var(--space-lg)', borderRadius: 'var(--radius-lg)', color: 'var(--red)', maxWidth: '100%', overflowX: 'auto' }}>
            {this.state.error?.toString()}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{ marginTop: 'var(--space-xl)', padding: 'var(--space-md) var(--space-xl)', background: 'var(--accent)', color: '#fff', borderRadius: 'var(--radius-md)', fontWeight: 600, border: 'none' }}
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const navItems = [
  { path: '/', label: 'Dashboard', icon: Home },
  { path: '/orchestrator', label: 'Orchestrator', icon: Activity },
  { path: '/capabilities', label: 'Capabilities', icon: Zap },
  { path: '/governance', label: 'Governance', icon: Activity },
  { path: '/firewall', label: 'Security', icon: Shield },
  { path: '/memory', label: 'Memory', icon: BarChart3 },
  { path: '/playground', label: 'Playground', icon: TerminalSquare },
  { path: '/docs', label: 'Docs', icon: BookOpen },
];

/* ─── Sidebar ─────────────────────────────────────────────────── */

function Sidebar({ open, onClose }) {
  const { health } = useDashboardData();
  const versionLabel = health?.version
    ? `v${String(health.version).replace(/^v/, '')}`
    : `v${import.meta.env.VITE_CUTCTX_VERSION || '0.29.0'}`;

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
      <div className="sidebar-footer-label">{versionLabel}</div>
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
          {theme === 'dark' ? (
            <span className="icon-sun">
              <Sun size={16} />
            </span>
          ) : (
            <span className="icon-moon">
              <Moon size={16} />
            </span>
          )}
        </button>
      </div>
    </header>
  );
}

/* ─── App Frame ───────────────────────────────────────────────── */

function AppFrame() {
  const searchInputRef = useRef(null);

  const { error } = useDashboardData();
  const [adminKey, setAdminKey] = useState(() => readStoredAdminKey());

  const handleSaveKey = () => {
    writeStoredAdminKey(adminKey);
    window.location.reload();
  };

  const isUnauthorized = error && error.includes('401');



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

  if (isUnauthorized) {
    return (
      <div style={{ padding: 'var(--space-3xl)', color: 'var(--text-primary)', background: 'var(--surface-0)', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', position: 'fixed', inset: 0, zIndex: 9999 }}>
        <h2 style={{ marginBottom: 'var(--space-md)' }}>Authentication Required</h2>
        <p style={{ marginBottom: 'var(--space-xl)', color: 'var(--text-secondary)' }}>The proxy requires an admin API key.</p>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <input 
            type="password" 
            placeholder="Enter CUTCTX_ADMIN_API_KEY" 
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            style={{ padding: '0.5rem 1rem', borderRadius: '4px', border: '1px solid var(--surface-2)', background: 'var(--surface-1)', color: 'var(--text-primary)', width: '300px' }}
          />
          <button 
            onClick={handleSaveKey}
            style={{ padding: '0.5rem 1rem', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            Save & Reload
          </button>
        </div>
      </div>
    );
  }

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
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/orchestrator" element={<Orchestrator />} />
              <Route path="/capabilities" element={<Capabilities />} />
              <Route path="/governance" element={<Governance searchQuery={searchQuery.toLowerCase()} />} />
              <Route path="/firewall" element={<Firewall searchQuery={searchQuery.toLowerCase()} />} />
              <Route path="/memory" element={<Memory searchQuery={searchQuery.toLowerCase()} />} />
              <Route path="/playground" element={<Playground />} />
              <Route path="/docs" element={<Docs />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const configuredBase = (import.meta.env.BASE_URL || '/').replace(/\/$/, '') || '/';
  const pathname = window.location.pathname;
  const basename = pathname.startsWith('/admin')
    ? '/admin'
    : pathname.startsWith('/dashboard')
      ? '/dashboard'
      : configuredBase === '/'
        ? '/'
        : configuredBase;

  return (
    <BrowserRouter basename={basename}>
      <ThemeProvider>
        <DashboardDataProvider>
          <AppFrame />
        </DashboardDataProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
