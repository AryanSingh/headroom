import { useState } from 'react';
import { Play, FileText, FastForward } from 'lucide-react';

export default function Playground() {
  const [inputPrompt, setInputPrompt] = useState('');
  const [simulated, setSimulated] = useState(false);
  const [tokensBefore, setTokensBefore] = useState('');
  const [tokensAfter, setTokensAfter] = useState('');
  const [error, setError] = useState('');

  const handleSimulate = () => {
    if (!inputPrompt.trim()) {
      setError('Please enter a prompt to simulate.');
      return;
    }
    setError('');
    setTokensBefore(inputPrompt);
    // Dummy compression simulation
    const compressed = inputPrompt
      .replace(/\s+/g, ' ')
      .replace(/please|kindly|could you/gi, '')
      .trim();
    setTokensAfter(compressed);
    setSimulated(true);
  };

  return (
    <div>
      <div className="page-header">
        <h2>Prompt Simulator</h2>
        <p className="text-secondary">Test and visualize prompt compression and tokenization.</p>
      </div>

      <div className="glass-panel mb-4">
        <label htmlFor="prompt-input" className="text-secondary flex items-center gap-2 mb-2">
          <FileText size={18} aria-hidden="true" /> Input Prompt
        </label>
        <textarea
          id="prompt-input"
          value={inputPrompt}
          onChange={(e) => {
            setInputPrompt(e.target.value);
            if (error) setError('');
          }}
          placeholder="Enter a complex prompt to see how the proxy optimizes it before hitting the upstream API..."
          rows={6}
          style={{ width: '100%', background: '#1e1e1e', color: '#fff', border: '1px solid #333', padding: '12px', borderRadius: '4px' }}
          aria-invalid={!!error}
        />
        <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ color: 'var(--danger-color)', fontSize: '14px' }}>
            {error && <span role="alert">{error}</span>}
          </div>
          <button 
            onClick={handleSimulate}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', background: '#58a6ff', color: '#0d1117', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            <Play size={16} aria-hidden="true" /> Simulate
          </button>
        </div>
      </div>

      {simulated && (
        <div className="grid grid-cols-2">
          <div className="glass-panel" style={{ borderRight: '1px solid #333', borderRadius: '8px 0 0 8px' }}>
            <h3 style={{ marginBottom: '16px', color: '#ff7b72' }}>Original Prompt ({tokensBefore.length} chars)</h3>
            <div style={{ background: '#0d1117', padding: '12px', borderRadius: '4px', minHeight: '150px', whiteSpace: 'pre-wrap' }}>
              {tokensBefore}
            </div>
          </div>
          <div className="glass-panel" style={{ borderRadius: '0 8px 8px 0' }}>
            <h3 style={{ marginBottom: '16px', color: '#7ee787', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FastForward size={18} /> Compressed Output ({tokensAfter.length} chars)
            </h3>
            <div style={{ background: '#0d1117', padding: '12px', borderRadius: '4px', minHeight: '150px', whiteSpace: 'pre-wrap' }}>
              {tokensAfter}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
