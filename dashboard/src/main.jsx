import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

import { adoptAdminKeyFromUrl } from './lib/admin-auth.js';

// Adopt admin key from URL if present
adoptAdminKeyFromUrl();

// Apply theme class immediately to prevent flash
try {
  const stored = localStorage.getItem('cutctxTheme');
  const theme = stored === 'light' ? 'light' : 'dark';
  document.documentElement.classList.add(theme);
} catch {
  document.documentElement.classList.add('dark');
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
