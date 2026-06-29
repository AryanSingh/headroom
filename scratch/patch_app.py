import re

with open("dashboard/src/App.jsx", "r") as f:
    content = f.read()

# Add readStoredAdminKey, writeStoredAdminKey to App.jsx imports if not there
if "readStoredAdminKey" not in content:
    content = "import { readStoredAdminKey, writeStoredAdminKey } from './lib/admin-auth';\n" + content

# Inject Auth overlay in AppFrame
auth_overlay = """
  const { error } = useDashboardData();
  const [adminKey, setAdminKey] = useState(() => readStoredAdminKey());

  const handleSaveKey = () => {
    writeStoredAdminKey(adminKey);
    window.location.reload();
  };

  const isUnauthorized = error && error.includes('401');

  if (isUnauthorized) {
    return (
      <div style={{ padding: 'var(--space-3xl)', color: 'var(--text-primary)', background: 'var(--surface-0)', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
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
"""

content = content.replace(
    "function AppFrame() {\n  const searchInputRef = useRef(null);",
    "function AppFrame() {\n  const searchInputRef = useRef(null);\n" + auth_overlay
)

# Wait, useDashboardData needs to be imported if not there
if "useDashboardData" not in content:
    content = "import { useDashboardData } from './lib/use-dashboard-data';\n" + content

with open("dashboard/src/App.jsx", "w") as f:
    f.write(content)
