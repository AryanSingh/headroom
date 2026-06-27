import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import {
  Activity,
  KeyRound,
  ArrowUpRight,
  BadgeInfo,
  BrainCircuit,
  Command,
  Flame,
  Network,
  Radar,
  Search,
  Shield,
  Sparkles,
  TerminalSquare,
} from 'lucide-react';
import Overview from './pages/Overview';
import Firewall from './pages/Firewall';
import Memory from './pages/Memory';
import Playground from './pages/Playground';
import Capabilities from './pages/Capabilities';
import { DashboardDataProvider } from './lib/dashboard-context';
import { readStoredAdminKey, writeStoredAdminKey } from './lib/admin-auth';
import { useDashboardData } from './lib/use-dashboard-data';
import { formatRelativeTime } from './lib/format';

const navItems = [
  { path: '/', label: 'Command Center', icon: Radar, description: 'Live proxy control surface' },
  { path: '/capabilities', label: 'Capabilities', icon: Sparkles, description: 'Full product surface map' },
  { path: '/firewall', label: 'Security', icon: Shield, description: 'Firewall and audit posture' },
  { path: '/memory', label: 'Memory', icon: BrainCircuit, description: 'Cross-session knowledge' },
  { path: '/playground', label: 'Playground', icon: TerminalSquare, description: 'Real compression simulator' },
];

function Sidebar({ searchQuery }) {
  const query = searchQuery.trim().toLowerCase();
  const items = navItems.filter((item) => {
    if (!query) {
      return true;
    }
    return `${item.label} ${item.description}`.toLowerCase().includes(query);
  });

  return (
    <aside className="sidebar-shell">
      <div className="brand-lockup">
        <div className="brand-mark">
          <Activity size={18} />
        </div>
        <div>
          <div className="eyebrow">Cutctx</div>
          <h1>Command Center</h1>
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-label">Navigation</div>
        <nav className="nav-stack">
          {items.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) => `nav-card ${isActive ? 'active' : ''}`}
              >
                <div className="nav-card-icon">
                  <Icon size={18} />
                </div>
                <div>
                  <div className="nav-card-title">{item.label}</div>
                  <div className="nav-card-copy">{item.description}</div>
                </div>
              </NavLink>
            );
          })}
        </nav>
      </div>

      <div className="sidebar-section sidebar-promo">
        <div className="sidebar-label">Product surfaces</div>
        <div className="promo-card">
          <div className="promo-row">
            <Command size={16} />
            Proxy, wrap, library, MCP
          </div>
          <div className="promo-row">
            <Network size={16} />
            Memory, CCR, firewall, savings
          </div>
          <div className="promo-row">
            <Flame size={16} />
            Multimodal optimization and live telemetry
          </div>
        </div>
      </div>
    </aside>
  );
}

function Topbar({ searchQuery, setSearchQuery, searchInputRef }) {
  const deferredQuery = useDeferredValue(searchQuery);
  const location = useLocation();
  const { health, lastUpdated } = useDashboardData();
  const [adminKey, setAdminKey] = useState(() => readStoredAdminKey());

  const currentNav = useMemo(
    () => navItems.find((item) => item.path === location.pathname) || navItems[0],
    [location.pathname],
  );

  return (
    <header className="topbar-shell">
      <div>
        <div className="eyebrow">Live workspace</div>
        <div className="topbar-title-row">
          <h2>{currentNav.label}</h2>
          <span className="status-pill">
            <span className={`status-dot ${health?.ready ? 'ok' : 'warn'}`} />
            {health?.status || 'connecting'}
          </span>
        </div>
        <p className="topbar-copy">{currentNav.description}</p>
      </div>

      <div className="topbar-tools">
        <label className="search-shell" aria-label="Search dashboard navigation">
          <Search size={16} />
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search pages and surfaces"
          />
        </label>

        <label className="auth-shell">
          <KeyRound size={16} />
          <input
            type="password"
            value={adminKey}
            onChange={(event) => {
              const nextValue = event.target.value;
              setAdminKey(nextValue);
              writeStoredAdminKey(nextValue.trim());
            }}
            placeholder="Optional admin key for protected actions"
          />
        </label>

        <div className="topbar-meta">
          <div className="meta-chip">
            <BadgeInfo size={14} />
            Local proxy
          </div>
          <div className="meta-chip">
            <ArrowUpRight size={14} />
            {formatRelativeTime(lastUpdated)}
          </div>
          <div className="meta-chip meta-chip-muted">
            Query: {deferredQuery || 'all surfaces'}
          </div>
          <div className={`meta-chip ${adminKey ? '' : 'meta-chip-muted'}`}>
            <KeyRound size={14} />
            {adminKey ? 'Admin key loaded' : 'No admin key'}
          </div>
        </div>
      </div>
    </header>
  );
}

function AppFrame() {
  const searchInputRef = useRef(null);
  const [searchQuery, setSearchQuery] = useState('');

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
    <div className="app-shell">
      <Sidebar searchQuery={searchQuery} />
      <div className="content-shell">
        <Topbar
          searchInputRef={searchInputRef}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
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
    <BrowserRouter>
      <DashboardDataProvider>
        <AppFrame />
      </DashboardDataProvider>
    </BrowserRouter>
  );
}
