import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import { Activity, Shield, BrainCircuit, Settings, Database } from 'lucide-react';
import Overview from './pages/Overview';
import Firewall from './pages/Firewall';
import Memory from './pages/Memory';

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
        <div className="nav-link" style={{ opacity: 0.5, cursor: 'not-allowed' }}>
          <Settings size={18} /> Settings
        </div>
      </nav>
    </div>
  );
}

function App() {
  return (
    <Router>
      <div className="app-container">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/firewall" element={<Firewall />} />
            <Route path="/memory" element={<Memory />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
