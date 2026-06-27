import { ImagePlus, Play, Sparkles, Wand2 } from 'lucide-react';
import { useState } from 'react';
import { readStoredAdminKey, writeStoredAdminKey } from '../lib/admin-auth';
import { getProxyUrl } from '../lib/api';
import { formatInteger, formatPercent } from '../lib/format';

const DEMO_PROMPT = [
  'Summarize the dashboard screenshot and the repeated build logs.',
  '',
  ...Array.from(
    { length: 120 },
    () => 'tool output chunk with stack traces, duplicated diagnostics, network retries, and repeated JSON payloads.',
  ),
].join('\n');

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error('Failed to read file.'));
    reader.readAsDataURL(file);
  });
}

function generateDemoImageDataUrl() {
  const canvas = document.createElement('canvas');
  canvas.width = 2048;
  canvas.height = 1365;

  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error('Canvas rendering is unavailable in this browser.');
  }

  const gradient = context.createLinearGradient(0, 0, canvas.width, canvas.height);
  gradient.addColorStop(0, '#08131c');
  gradient.addColorStop(0.6, '#0f2432');
  gradient.addColorStop(1, '#12384b');
  context.fillStyle = gradient;
  context.fillRect(0, 0, canvas.width, canvas.height);

  context.fillStyle = 'rgba(120, 183, 255, 0.16)';
  context.beginPath();
  context.arc(320, 240, 220, 0, Math.PI * 2);
  context.fill();
  context.beginPath();
  context.arc(1650, 180, 300, 0, Math.PI * 2);
  context.fill();

  context.fillStyle = '#e7f5ff';
  context.font = '700 64px Inter, Arial, sans-serif';
  context.fillText('Cutctx Command Center', 96, 112);
  context.font = '400 30px Inter, Arial, sans-serif';
  context.fillStyle = '#9db9c8';
  context.fillText('Live proxy savings, multimodal compression, and request telemetry', 96, 160);

  const cards = [
    { x: 96, y: 220, w: 420, h: 210, title: 'Tokens saved', value: '483.9k', accent: '#54d2c6' },
    { x: 546, y: 220, w: 420, h: 210, title: 'Compression USD', value: '$1.210', accent: '#78b7ff' },
    { x: 996, y: 220, w: 420, h: 210, title: 'Provider cache', value: '919.7k', accent: '#f2b46b' },
    { x: 1446, y: 220, w: 506, h: 210, title: 'Proxy health', value: 'healthy', accent: '#9ce7dd' },
  ];

  for (const card of cards) {
    context.fillStyle = 'rgba(7, 16, 24, 0.72)';
    context.fillRect(card.x, card.y, card.w, card.h);
    context.strokeStyle = 'rgba(151, 190, 214, 0.18)';
    context.lineWidth = 2;
    context.strokeRect(card.x, card.y, card.w, card.h);
    context.fillStyle = card.accent;
    context.fillRect(card.x + 24, card.y + 28, 10, card.h - 56);
    context.fillStyle = '#9db9c8';
    context.font = '500 26px Inter, Arial, sans-serif';
    context.fillText(card.title, card.x + 56, card.y + 62);
    context.fillStyle = '#edf5fb';
    context.font = '700 56px Space Grotesk, Inter, Arial, sans-serif';
    context.fillText(card.value, card.x + 56, card.y + 142);
    context.fillStyle = '#6f8493';
    context.font = '400 22px Inter, Arial, sans-serif';
    context.fillText('Live dashboard sample for multimodal verification', card.x + 56, card.y + 182);
  }

  context.fillStyle = 'rgba(7, 16, 24, 0.78)';
  context.fillRect(96, 488, 1856, 760);
  context.strokeStyle = 'rgba(151, 190, 214, 0.18)';
  context.strokeRect(96, 488, 1856, 760);

  context.fillStyle = '#edf5fb';
  context.font = '600 34px Inter, Arial, sans-serif';
  context.fillText('Repeated build trace', 132, 544);

  context.font = '400 24px Menlo, Monaco, Consolas, monospace';
  const logLines = [
    '[proxy] POST /v1/compress 200 in 148ms image:preserve router:noop tokens_saved=680',
    '[dashboard] playground sample loaded with admin auth and real proxy target',
    '[stats] compression attribution fallback enabled for sparse source buckets',
    '[browser] command center route loaded with zero console errors',
    '[memory] local backend initialized and ready',
    '[firewall] protected endpoints require admin auth',
    '[codex] websocket aliases registered for responses API',
    '[savings] image metrics 1020 -> 340 tokens, preserved detail=high',
  ];

  let lineY = 604;
  for (let group = 0; group < 9; group += 1) {
    for (const line of logLines) {
      context.fillStyle = group % 2 === 0 ? '#b8cedc' : '#8fb0c3';
      context.fillText(line, 132, lineY);
      lineY += 42;
      if (lineY > 1190) {
        break;
      }
    }
    if (lineY > 1190) {
      break;
    }
  }

  return canvas.toDataURL('image/png');
}

export default function Playground() {
  const [adminKey, setAdminKey] = useState(() => readStoredAdminKey());
  const [prompt, setPrompt] = useState('');
  const [model, setModel] = useState('gpt-4o');
  const [imageDataUrl, setImageDataUrl] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleImageChange = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      setImageDataUrl('');
      return;
    }

    try {
      const dataUrl = await fileToDataUrl(file);
      setImageDataUrl(String(dataUrl));
      setError('');
    } catch (readError) {
      setError(readError.message || 'Failed to read the selected image.');
    }
  };

  const handleLoadDemo = () => {
    try {
      setImageDataUrl(generateDemoImageDataUrl());
      if (!prompt.trim()) {
        setPrompt(DEMO_PROMPT);
      }
      setError('');
    } catch (demoError) {
      setError(demoError.message || 'Failed to generate the demo image.');
    }
  };

  const handleRun = async () => {
    if (!prompt.trim()) {
      setError('Enter a prompt before running the playground.');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    const content = [{ type: 'text', text: prompt }];
    if (imageDataUrl) {
      content.push({
        type: 'image_url',
        image_url: {
          url: imageDataUrl,
          detail: 'high',
        },
      });
    }

    try {
      const response = await fetch(getProxyUrl('/v1/compress'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(adminKey.trim() ? { 'x-cutctx-admin-key': adminKey.trim() } : {}),
        },
        body: JSON.stringify({
          model,
          compress_user_messages: true,
          messages: [
            {
              role: 'user',
              content,
            },
          ],
        }),
      });

      if (!response.ok) {
        throw new Error(
          `Compression request failed with ${response.status}. If this proxy requires admin auth, load an admin key in the top bar first.`,
        );
      }

      const payload = await response.json();
      setResult(payload);
    } catch (requestError) {
      setError(requestError.message || 'Compression request failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-stack">
      <div className="page-header-card">
        <div>
          <div className="eyebrow">Interactive verification</div>
          <h1>Real compression playground</h1>
          <p>
            This page hits the live <code>/v1/compress</code> endpoint and supports multimodal payloads,
            so users can inspect actual transforms and savings.
          </p>
        </div>
        <div className="hero-sidecard">
          <div className="hero-sidecard-label">What it proves</div>
          <div className="hero-sidecard-value">Real endpoint</div>
          <p>Prompt, transforms, before/after tokens, and image metrics come from the running proxy.</p>
        </div>
      </div>

      {error && <div className="alert-card">{error}</div>}

      <div className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Input</div>
              <h2>Build a compression request</h2>
            </div>
          </div>

          <div className="form-grid">
            <label className="field">
              <span>Admin key</span>
              <input
                type="password"
                value={adminKey}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setAdminKey(nextValue);
                  writeStoredAdminKey(nextValue);
                }}
                placeholder="Uses the same key as the top bar"
              />
            </label>

            <label className="field">
              <span>Model</span>
              <select value={model} onChange={(event) => setModel(event.target.value)}>
                <option value="gpt-4o">gpt-4o</option>
                <option value="gpt-5.4">gpt-5.4</option>
                <option value="gpt-5.4-mini">gpt-5.4-mini</option>
              </select>
            </label>

            <label className="field field-file">
              <span>Optional image</span>
              <input type="file" accept="image/*" onChange={handleImageChange} />
            </label>
          </div>

          <div className="playground-actions">
            <button className="secondary-button" onClick={handleLoadDemo} type="button">
              <ImagePlus size={16} />
              Load sample multimodal image
            </button>
            {imageDataUrl && (
              <div className="meta-chip">
                <ImagePlus size={14} />
                Image attached
              </div>
            )}
          </div>

          <label className="field">
            <span>Prompt</span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={8}
              placeholder="Paste a long tool output, code, transcript, or ask a multimodal question."
            />
          </label>

          <div className="playground-actions">
            <button className="primary-button" onClick={handleRun} disabled={loading}>
              <Play size={16} />
              {loading ? 'Compressing…' : 'Run live compression'}
            </button>
          </div>
        </section>

        <aside className="panel panel-side">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Tips</div>
              <h2>Use cases</h2>
            </div>
          </div>

          <div className="stack-list">
            <StatusBullet
              title="Long tool output"
              detail="Paste repeated JSON or logs to see text compression."
            />
            <StatusBullet
              title="Multimodal payload"
              detail="Attach an image or use the built-in sample to surface image metrics separately."
            />
            <StatusBullet
              title="Browser QA friendly"
              detail="The sample image path makes end-to-end multimodal verification possible without a native file picker."
            />
          </div>
        </aside>
      </div>

      <div className="metric-grid metric-grid-four">
        <MetricCard
          icon={<Sparkles size={18} />}
          label="Tokens before"
          value={result ? formatInteger(result.tokens_before) : '—'}
          note="Raw request estimate"
        />
        <MetricCard
          icon={<Wand2 size={18} />}
          label="Tokens after"
          value={result ? formatInteger(result.tokens_after) : '—'}
          note="Post-compression estimate"
        />
        <MetricCard
          icon={<Sparkles size={18} />}
          label="Tokens saved"
          value={result ? formatInteger(result.tokens_saved) : '—'}
          note={result ? formatPercent((1 - result.compression_ratio) * 100) : 'Real savings delta'}
        />
        <MetricCard
          icon={<ImagePlus size={18} />}
          label="Image savings"
          value={result?.image_metrics ? formatInteger(result.image_metrics.tokens_saved) : '—'}
          note={result?.image_metrics?.technique || 'Only appears for image payloads'}
        />
      </div>

      <div className="dashboard-grid">
        <section className="panel panel-wide">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Output</div>
              <h2>Compressed request payload</h2>
            </div>
          </div>
          <pre className="code-panel">
            {result ? JSON.stringify(result.messages, null, 2) : 'Run a request to inspect the transformed payload.'}
          </pre>
        </section>

        <aside className="panel panel-side">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Transforms</div>
              <h2>Applied steps</h2>
            </div>
          </div>
          <div className="chip-stack">
            {Array.isArray(result?.transforms_applied) && result.transforms_applied.length > 0 ? (
              result.transforms_applied.map((transform) => (
                <div key={transform} className="chip-card">
                  <div className="chip-title">{transform}</div>
                </div>
              ))
            ) : (
              <div className="empty-copy">No transforms yet.</div>
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}

function MetricCard({ icon, label, value, note }) {
  return (
    <article className="metric-card">
      <div className="metric-header">
        <span className="metric-label">{label}</span>
        <div className="metric-icon">{icon}</div>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-footnote">{note}</div>
    </article>
  );
}

function StatusBullet({ title, detail }) {
  return (
    <article className="status-bullet">
      <strong>{title}</strong>
      <p>{detail}</p>
    </article>
  );
}
