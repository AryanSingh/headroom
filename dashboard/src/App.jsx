import { readStoredAdminKey, writeStoredAdminKey } from './lib/admin-auth';
import { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  BookOpen,
  Globe,
  Home,
  History,
  Moon,
  Package,
  PanelLeftOpen,
  PiggyBank,
  Search,
  Shield,
  Sun,
  TerminalSquare,
  Zap,
} from 'lucide-react';
import Overview from './pages/Overview';
import Savings from './pages/Savings';
import Firewall from './pages/Firewall';
import Governance from './pages/Governance';
import Memory from './pages/Memory';
import Playground from './pages/Playground';
import Capabilities from './pages/Capabilities';
import Docs from './pages/Docs';
import Orchestrator from './pages/Orchestrator';
import Replay from './pages/Replay';
import { PageHeader } from './components/PageHeader';
import { StatePanel } from './components/StatePanel';
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
  { path: '/savings', label: 'Savings', icon: PiggyBank },
  { path: '/orchestrator', label: 'Orchestrator', icon: Activity },
  { path: '/capabilities', label: 'Capabilities', icon: Zap },
  { path: '/governance', label: 'Governance', icon: Activity },
  { path: '/firewall', label: 'Security', icon: Shield },
  { path: '/memory', label: 'Memory', icon: BarChart3 },
  { path: '/replay', label: 'Replay', icon: History },
  { path: '/playground', label: 'Playground', icon: TerminalSquare },
  { path: '/docs', label: 'Docs', icon: BookOpen },
];

/* ─── Sidebar ─────────────────────────────────────────────────── */

function Sidebar({ open, onClose }) {
  const { health } = useDashboardData();
  const versionLabel = health?.version
    ? `v${String(health.version).replace(/^v/, '')}`
    : `v${import.meta.env.VITE_CUTCTX_VERSION || 'unknown'}`;

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
          <nav className="nav-stack" aria-label="Main Navigation">
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
              <Globe size={12} />
              Proxy, wrap, library, MCP
            </div>
            <div className="promo-row">
              <Package size={12} />
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
  sidebarToggleRef,
  onToggleSidebar,
}) {
  const location = useLocation();
  const { health } = useDashboardData();
  const { theme, toggleTheme } = useTheme();

  const currentNav = useMemo(
    () => navItems.find((item) => item.path === location.pathname) || navItems[0],
    [location.pathname],
  );

  const searchEnabled = useMemo(() => {
    return ['/', '/orchestrator', '/governance', '/firewall', '/memory', '/replay'].includes(
      location.pathname,
    );
  }, [location.pathname]);

  useEffect(() => {
    document.title = currentNav ? `${currentNav.label} — Cutctx` : 'Cutctx Dashboard';
  }, [currentNav]);

  return (
    <header className="topbar-shell">
      <div className="topbar-left">
        <button
          ref={sidebarToggleRef}
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
        {searchEnabled ? (
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
        ) : (
          <div className="search-shell" style={{ opacity: 0.5, cursor: 'not-allowed' }} title="Search not available on this page">
            <Search size={14} />
            <input type="text" placeholder="Search unavailable" disabled style={{ cursor: 'not-allowed' }} />
          </div>
        )}

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
  const sidebarToggleRef = useRef(null);

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
      if (e.matches) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };
    handler(mq);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev);
  }, []);

  const closeSidebar = useCallback(() => {
    if (isMobile) {
      setSidebarOpen(false);
      sidebarToggleRef.current?.focus();
    }
  }, [isMobile]);

  useEffect(() => {
    if (!isMobile || !sidebarOpen) {
      return undefined;
    }
    const handleDrawerKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeSidebar();
      }
    };
    window.addEventListener('keydown', handleDrawerKeyDown);
    return () => window.removeEventListener('keydown', handleDrawerKeyDown);
  }, [closeSidebar, isMobile, sidebarOpen]);

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
      <main className="authentication-surface" data-testid="authentication-surface">
        <section className="authentication-card" aria-label="Connect to Cutctx">
          <PageHeader
            eyebrow="Operator access"
            title="Connect to Cutctx"
            description="Enter the admin key configured for this proxy to continue to the command center."
          />
          <StatePanel tone="error" icon={Shield} title="Authentication required">
            The proxy requires an admin API key before it can return dashboard data.
          </StatePanel>
          <form
            className="authentication-form"
            onSubmit={(event) => {
              event.preventDefault();
              handleSaveKey();
            }}
          >
            <label className="authentication-field" htmlFor="admin-api-key">
              <span>Admin API key</span>
              <input
                id="admin-api-key"
                type="password"
                placeholder="Enter CUTCTX_ADMIN_API_KEY"
                value={adminKey}
                onChange={(event) => setAdminKey(event.target.value)}
              />
            </label>
            <button className="primary-button" type="submit">
              Save & Reload
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <div className={`app-shell ${!sidebarOpen && !isMobile ? 'sidebar-collapsed' : ''}`}>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <Sidebar open={sidebarOpen} onClose={closeSidebar} />
      <div className="content-shell">
        <Topbar
          searchInputRef={searchInputRef}
          sidebarToggleRef={sidebarToggleRef}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          onToggleSidebar={toggleSidebar}
        />
        <main className="page-shell" id="main-content" tabIndex="-1">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Overview searchQuery={searchQuery} />} />
              <Route path="/savings" element={<Savings />} />
              <Route path="/orchestrator" element={<Orchestrator searchQuery={searchQuery} />} />
              <Route path="/capabilities" element={<Capabilities />} />
              <Route path="/governance" element={<Governance searchQuery={searchQuery.toLowerCase()} />} />
              <Route path="/firewall" element={<Firewall searchQuery={searchQuery.toLowerCase()} />} />
              <Route path="/memory" element={<Memory searchQuery={searchQuery.toLowerCase()} />} />
              <Route path="/replay" element={<Replay />} />
              <Route path="/playground" element={<Playground />} />
              <Route path="/docs" element={<Docs />} />
              <Route path="*" element={<Navigate to="/" replace />} />
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
