/**
 * AIOutputCard — Standard wrapper for all AI-generated clinical content.
 *
 * REQUIRED: Every AI-generated output in the UI must use this component.
 * Visually distinguishes AI output from verified clinical data.
 * Shows AI badge, confidence indicator, and requires-review flag.
 *
 * Owner agent: ui-designer-agent
 */

import React from 'react';
import { ConfidenceIndicator } from './ConfidenceIndicator';

/**
 * @param {object} props
 * @param {string} props.title - The clinical finding or report title
 * @param {number} [props.confidence] - 0-1 confidence score
 * @param {React.ReactNode} props.content - The AI-generated content
 * @param {function} [props.onAcknowledge] - Called when clinician acknowledges the finding
 * @param {boolean} [props.isEmergency] - True for emergency/critical findings
 */
export function AIOutputCard({ title, confidence, content, onAcknowledge, isEmergency }) {
  return (
    <div
      className={`ai-output-card ${isEmergency ? 'ai-output-card--emergency' : ''}`}
      role="region"
      aria-label={`AI-generated ${title}`}
      style={{
        border: `2px solid var(--color-ai-border)`,
        background: 'var(--color-ai-bg)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-4)',
      }}
    >
      {/* AI Badge — always visible, always explains this is AI-generated */}
      <div className="ai-badge" style={{ marginBottom: 'var(--space-3)' }}>
        <span aria-hidden="true">🤖</span>
        <strong style={{ color: 'var(--color-ai-badge)', marginLeft: 'var(--space-2)' }}>
          AI-generated · Requires clinical review
        </strong>
        {confidence !== undefined && (
          <ConfidenceIndicator value={confidence} />
        )}
      </div>

      {/* AI-generated content */}
      <div className="ai-content">
        {content}
      </div>

      {/* Acknowledgement — required for findings that need explicit sign-off */}
      {onAcknowledge && (
        <button
          onClick={onAcknowledge}
          className="acknowledge-btn"
          aria-label="Acknowledge this AI finding"
          style={{
            marginTop: 'var(--space-4)',
            minHeight: 'var(--min-tap-target)',
            minWidth: 'var(--min-tap-target)',
            padding: '0 var(--space-4)',
          }}
        >
          I have reviewed this AI finding
        </button>
      )}
    </div>
  );
}
