import re
from pathlib import Path

content = Path("dashboard/src/pages/Overview.jsx").read_text()

# 1. Update imports
content = content.replace(
    "import { useDashboardData } from '../lib/use-dashboard-data';",
    "import { useDashboardData, fetchDashboardJson } from '../lib/use-dashboard-data';\nimport { useEffect } from 'react';\nimport { Calendar, Clock, Activity } from 'lucide-react';"
)

# 2. Modify TrendChart
trend_chart_header_regex = re.compile(r'<div className="trend-chart-header">.*?<div className="trend-chart">', re.DOTALL)
content = re.sub(
    r'function TrendChart\(\{ stats, historyData \}\) \{.*?\n  const buckets = useMemo\(',
    r'''function TrendChart({ stats, historyData, duration }) {
  const [referenceTime, setReferenceTime] = useState(() => Date.now());
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const recentRequestsSource = stats?.recent_requests;
  
  const mode = duration === 'session' ? 'session' : 'historical';
  const period = duration === 'daily' ? '24h' : duration === 'weekly' ? '7d' : '30d';

  useEffect(() => {
    setReferenceTime(Date.now());
    setHoveredIndex(null);
  }, [duration]);

  const buckets = useMemo(''',
    content,
    flags=re.DOTALL
)

content = trend_chart_header_regex.sub(
    r'''<div className="trend-chart-header">
        {activeBucket ? (
          <div className="trend-hover-summary" style={{ marginLeft: 'auto' }}>
            <div className="trend-hover-label">{activeBucket.label}</div>
            <div className="trend-hover-metrics">
              <span>{formatInteger(activeBucket.tokens)} tokens saved</span>
              <span>
                {activeBucket.hasRequestData
                  ? `${formatInteger(activeBucket.requests)} requests`
                  : 'Request count unavailable'}
              </span>
              <span>
                {activeBucketTopModels.length > 0
                  ? `Top model: ${activeBucketTopModels
                      .map((entry) => `${entry.model} (${formatInteger(entry.tokens)})`)
                      .join(', ')}`
                  : 'Model mix unavailable'}
              </span>
            </div>
          </div>
        ) : null}
      </div>

      <div className="trend-chart">''',
    content
)

# 3. Update Overview function
overview_start_regex = re.compile(r'export default function Overview\(\) \{[\s\S]*?const activeCompressionPercent.*?;', re.DOTALL)
new_overview = r'''export default function Overview() {
  const {
    stats,
    historyData,
    historyLoading,
    historyError,
    loading: contextLoading,
    error: contextError,
  } = useDashboardData();

  const [duration, setDuration] = useState('lifetime'); // 'session', 'lifetime', 'daily', 'weekly', 'monthly'
  const [durationData, setDurationData] = useState(null);
  const [durationLoading, setDurationLoading] = useState(true);
  const [durationError, setDurationError] = useState(null);

  useEffect(() => {
    let active = true;
    
    async function fetchData() {
      setDurationLoading(true);
      setDurationError(null);
      
      if (duration === 'session') {
        if (historyData?.display_session) {
          setDurationData(historyData.display_session);
        }
        setDurationLoading(false);
        return;
      }
      
      if (duration === 'lifetime') {
        if (historyData?.lifetime) {
          setDurationData(historyData.lifetime);
        }
        setDurationLoading(false);
        return;
      }
      
      try {
        const data = await fetchDashboardJson(`/stats-history?series=${duration}`);
        if (active) {
          setDurationData(data?.history_summary || data?.lifetime || null);
        }
      } catch (err) {
        if (active) {
          setDurationError(err.message || String(err));
        }
      } finally {
        if (active) {
          setDurationLoading(false);
        }
      }
    }
    
    fetchData();
    
    return () => {
      active = false;
    };
  }, [duration, historyData]);

  const loading = contextLoading || (durationLoading && !durationData);
  const error = contextError || durationError;

  const tokensSaved = durationData?.tokens_saved || 0;
  const savingsUsd = durationData?.compression_savings_usd || 0;
  const requestsCount = durationData?.requests || 0;
  const totalInputTokens = durationData?.total_input_tokens || 1;
  const savingsPercent = durationData?.savings_percent != null 
    ? durationData.savings_percent 
    : ((tokensSaved / totalInputTokens) * 100);

  const effectiveTokensSaved = tokensSaved;
  const effectiveRequests = requestsCount;
  const effectiveSavingsUsd = savingsUsd;
  const effectiveSavingsPercent = savingsPercent;

  const moneySavedFootnote = duration === 'session' ? 'Current proxy-session savings' : `Estimated savings for the ${duration} period`;
  const requestsFootnote = `${formatInteger(effectiveRequests)} requests in the ${duration} period`;

  const tokens = stats?.tokens || {};
  const activeCompressionPercent =
    tokens.active_savings_percent != null ? Number(tokens.active_savings_percent || 0) : null;'''
content = overview_start_regex.sub(new_overview, content)

# 4. Insert tabs in render
content = content.replace(
    '''<div className="metric-grid metric-grid-four">''',
    '''<div className="tab-group" style={{ marginBottom: 'var(--space-md)' }}>
        <button 
          className={`tab-button ${duration === 'session' ? 'active' : ''}`}
          onClick={() => setDuration('session')}
        >
          <Activity size={16} /> Current Session
        </button>
        <button 
          className={`tab-button ${duration === 'daily' ? 'active' : ''}`}
          onClick={() => setDuration('daily')}
        >
          <Clock size={16} /> Last 24 Hours
        </button>
        <button 
          className={`tab-button ${duration === 'weekly' ? 'active' : ''}`}
          onClick={() => setDuration('weekly')}
        >
          <Calendar size={16} /> Last 7 Days
        </button>
        <button 
          className={`tab-button ${duration === 'monthly' ? 'active' : ''}`}
          onClick={() => setDuration('monthly')}
        >
          <Calendar size={16} /> Last 30 Days
        </button>
        <button 
          className={`tab-button ${duration === 'lifetime' ? 'active' : ''}`}
          onClick={() => setDuration('lifetime')}
        >
          <PiggyBank size={16} /> Lifetime (All Time)
        </button>
      </div>
      
      <div className="metric-grid metric-grid-four">'''
)

# 5. Fix remaining references like recentRequests, sourceRows, etc.
# These will still read from `stats`, which is fine because `stats` is the live backend data.
# However, `TrendChart` call needs to be updated.
content = content.replace(
    '<TrendChart stats={stats} historyData={historyData} />',
    '<TrendChart stats={stats} historyData={historyData} duration={duration} />'
)

Path("dashboard/src/pages/Overview.jsx").write_text(content)
