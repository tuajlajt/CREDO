/**
 * DrugCheck — Drug interaction checking interface.
 *
 * Allows entering a medication list and viewing interaction results.
 * Major interactions shown prominently with alternative suggestions.
 * Always includes pharmacist review disclaimer.
 *
 * Owner agent: ui-designer-agent
 */

import React, { useState } from 'react';
import { DrugInteractionAlert } from '../components/DrugInteractionAlert';

export function DrugCheck() {
  const [drugInput, setDrugInput] = useState('');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleCheck = async () => {
    const drugNames = drugInput.split('\n').map(d => d.trim()).filter(Boolean);
    if (drugNames.length === 0) return;

    setLoading(true);
    setError(null);
    try {
      // TODO: call POST /drug-check/ API
      const response = await fetch('/drug-check/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ drug_names: drugNames }),
      });
      if (!response.ok) throw new Error(`API error: ${response.status}`);
      setReport(await response.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ fontFamily: 'var(--font-clinical)', maxWidth: '600px', padding: 'var(--space-6)' }}>
      <h1 style={{ fontSize: '20px', fontWeight: 600 }}>Drug Interaction Check</h1>

      <div style={{ marginTop: 'var(--space-4)' }}>
        <label htmlFor="drug-input" style={{ display: 'block', marginBottom: 'var(--space-2)' }}>
          Enter medications (one per line):
        </label>
        <textarea
          id="drug-input"
          value={drugInput}
          onChange={(e) => setDrugInput(e.target.value)}
          rows={6}
          style={{
            width: '100%',
            padding: 'var(--space-3)',
            fontFamily: 'var(--font-clinical)',
            fontSize: 'var(--text-base)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid #d1d5db',
          }}
          placeholder="e.g.&#10;Warfarin&#10;Aspirin&#10;Lisinopril"
        />
      </div>

      <button
        onClick={handleCheck}
        disabled={loading}
        style={{
          marginTop: 'var(--space-4)',
          minHeight: 'var(--min-tap-target)',
          padding: '0 var(--space-6)',
          background: 'var(--color-routine)',
          color: '#ffffff',
          border: 'none',
          borderRadius: 'var(--radius-sm)',
          cursor: loading ? 'wait' : 'pointer',
        }}
      >
        {loading ? 'Checking...' : 'Check Interactions'}
      </button>

      {error && (
        <p role="alert" style={{ color: 'var(--color-emergency)', marginTop: 'var(--space-4)' }}>
          Error: {error}
        </p>
      )}

      {report && (
        <div style={{ marginTop: 'var(--space-6)' }}>
          {report.major_interactions?.length > 0 && (
            <DrugInteractionAlert interactions={report.major_interactions} severity="major" />
          )}
          {report.interactions?.filter(i => i.severity === 'moderate').length > 0 && (
            <DrugInteractionAlert
              interactions={report.interactions.filter(i => i.severity === 'moderate')}
              severity="moderate"
            />
          )}
          {report.interactions?.length === 0 && (
            <p style={{ color: 'var(--color-normal)' }}>
              ✓ No significant interactions identified in database.
            </p>
          )}
          <p style={{ fontSize: 'var(--text-label)', color: '#6b7280', marginTop: 'var(--space-4)' }}>
            {report.disclaimer}
          </p>
        </div>
      )}
    </div>
  );
}
