/**
 * RadiologyReport — View and interact with an AI-generated radiology report.
 *
 * Shows: AI report draft in amber card, technique/findings/impression sections,
 * editing interface for radiologist review, sign & finalise workflow.
 *
 * Owner agent: ui-designer-agent
 */

import React, { useState } from 'react';
import { AIOutputCard } from '../components/AIOutputCard';
import { CriticalAlert } from '../components/CriticalAlert';

/**
 * @param {object} props
 * @param {object} props.report - RadiologyReport object from API
 * @param {function} props.onFinalise - Called when radiologist signs off
 */
export function RadiologyReport({ report, onFinalise }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [acknowledgedAt, setAcknowledgedAt] = useState(null);

  if (!report) {
    return <p style={{ color: '#6b7280' }}>No report loaded.</p>;
  }

  const hasCriticalFindings = report.critical_findings?.length > 0;

  return (
    <div style={{ fontFamily: 'var(--font-clinical)', maxWidth: '800px' }}>
      <h1 style={{ fontSize: '20px', fontWeight: 600 }}>
        {report.modality} Report — AI Draft
      </h1>

      {/* Critical findings — shown first, before main report */}
      {hasCriticalFindings && report.critical_findings.map((finding, i) => (
        <CriticalAlert
          key={i}
          finding={finding}
          onAcknowledge={(ts) => { setAcknowledgedAt(ts); }}
          acknowledgedAt={acknowledgedAt}
        />
      ))}

      {/* AI report card */}
      <AIOutputCard
        title={`${report.modality} Report`}
        confidence={report.confidence}
        isEmergency={hasCriticalFindings}
        content={
          <div>
            <section>
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#374151' }}>Technique</h3>
              <p>{report.technique || 'Not specified'}</p>
            </section>
            <section style={{ marginTop: 'var(--space-4)' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#374151' }}>Findings</h3>
              <p style={{ whiteSpace: 'pre-wrap' }}>{report.findings}</p>
            </section>
            <section style={{ marginTop: 'var(--space-4)' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#374151' }}>Impression</h3>
              <p>{report.impression}</p>
            </section>
          </div>
        }
        onAcknowledge={() => setAcknowledged(true)}
      />

      {/* Disclaimer — always visible */}
      <p style={{ fontSize: 'var(--text-label)', color: '#6b7280', marginTop: 'var(--space-4)' }}>
        {report.disclaimer}
      </p>

      {/* Actions */}
      <div style={{ marginTop: 'var(--space-6)', display: 'flex', gap: 'var(--space-4)' }}>
        <button style={{ minHeight: 'var(--min-tap-target)', padding: '0 var(--space-6)' }}>
          Edit Report
        </button>
        <button
          onClick={onFinalise}
          disabled={hasCriticalFindings && !acknowledgedAt}
          style={{
            minHeight: 'var(--min-tap-target)',
            padding: '0 var(--space-6)',
            background: 'var(--color-routine)',
            color: '#ffffff',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: hasCriticalFindings && !acknowledgedAt ? 'not-allowed' : 'pointer',
          }}
        >
          Sign &amp; Finalise
        </button>
      </div>
    </div>
  );
}
