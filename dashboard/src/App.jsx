import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import { Activity, Shield, BrainCircuit, Settings, Database, TerminalSquare, Search, X } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import Overview from './pages/Overview';
import Firewall from './pages/Firewall';
import Memory from './pages/Memory';
import Playground from './pages/Playground';

function Sidebar() {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>
          <Activity color="#58a6ff" /> Headroom
        </h1>
      </div>
      <nav>
        <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Database size={18} /> Overview
        </NavLink>
        <NavLink to="/firewall" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Shield size={18} /> Firewall
        </NavLink>
        <NavLink to="/memory" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <BrainCircuit size={18} /> Memory & Learn
        </NavLink>
        <NavLink to="/playground" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <TerminalSquare size={18} /> Prompt Simulator
        </NavLink>
        <div className="nav-link" aria-disabled="true" style={{ opacity: 0.5, cursor: 'not-allowed' }}>
          <Settings size={18} aria-hidden="true" /> Settings
        </div>
      </nav>
    </div>
  );
}

function Topbar({ searchInputRef }) {
  return (
    <div className="topbar" style={{ padding: '16px 48px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div style={{ position: 'relative', width: '300px' }}>
        <Search size={16} style={{ position: 'absolute', left: '12px', top: '10px', color: 'var(--text-secondary)' }} aria-hidden="true" />
        <input 
          ref={searchInputRef}
          type="text" 
          aria-label="Search"
          placeholder="Search... (Press '/' to focus)" 
          style={{ width: '100%', padding: '8px 12px 8px 36px', background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-primary)' }}
        />
      </div>
      <div style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
        Press <kbd style={{ background: '#333', padding: '2px 6px', borderRadius: '4px' }}>?</kbd> for help
      </div>
    </div>
  );
}

function HelpModal({ isOpen, onClose }) {
  if (!isOpen) return null;
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="help-title" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div className="glass-panel" style={{ width: '400px', position: 'relative' }}>
        <button onClick={onClose} aria-label="Close help" style={{ position: 'absolute', top: '16px', right: '16px', background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>
          <X size={20} aria-hidden="true" />
        </button>
        <h3 id="help-title" style={{ marginBottom: '16px', color: '#fff' }}>Keyboard Shortcuts</h3>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          <li style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span>Focus Search</span>
            <kbd style={{ background: '#333', padding: '2px 6px', borderRadius: '4px' }}>/</kbd>
          </li>
          <li style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span>Show Help</span>
            <kbd style={{ background: '#333', padding: '2px 6px', borderRadius: '4px' }}>?</kbd>
          </li>
          <li style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Close Modals</span>
            <kbd style={{ background: '#333', padding: '2px 6px', borderRadius: '4px' }}>Escape</kbd>
          </li>
        </ul>
      </div>
    </div>
  );
}

function App() {
  const [showHelp, setShowHelp] = useState(false);
  const searchInputRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      // Don't trigger shortcuts if user is typing in an input or textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        if (e.key === 'Escape') {
          e.target.blur();
        }
        return;
      }

      if (e.key === '?') {
        e.preventDefault();
        setShowHelp(true);
      } else if (e.key === '/') {
        e.preventDefault();
        searchInputRef.current?.focus();
      } else if (e.key === 'Escape') {
        setShowHelp(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <Router>
      <div className="app-container">
        <Sidebar />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh' }}>
          <Topbar searchInputRef={searchInputRef} />
          <main className="main-content" style={{ flex: 1, overflowY: 'auto' }}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/firewall" element={<Firewall />} />
              <Route path="/memory" element={<Memory />} />
              <Route path="/playground" element={<Playground />} />
            </Routes>
          </main>
        </div>
        <HelpModal isOpen={showHelp} onClose={() => setShowHelp(false)} />
      </div>
    </Router>
  );
}

export default App;
