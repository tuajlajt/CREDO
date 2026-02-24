/**
 * CriticalAlert — Emergency finding alert requiring explicit acknowledgement.
 *
 * RULES:
 * - Full-width, red background — cannot be missed
 * - Requires explicit acknowledgement click before dismissing
 * - Acknowledgement timestamp is logged
 * - Uses aria-live="assertive" — screen readers announce immediately
 * - Z-index: var(--z-emergency) — always on top
 *
 * Owner agent: ui-designer-agent
 */

import React from 'react';

/**
 * @param {object} props
 * @param {string} props.finding - Description of the critical finding
 * @param {function} props.onAcknowledge - Called with timestamp when acknowledged
 * @param {string|null} props.acknowledgedAt - ISO timestamp if already acknowledged
 */
export function CriticalAlert({ finding, onAcknowledge, acknowledgedAt }) {
  const handleAcknowledge = () => {
    const timestamp = new Date().toISOString();
    onAcknowledge(timestamp);
  };

  return (
    <div
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      style={{
        background: 'var(--color-emergency)',
        color: '#ffffff',
        padding: 'var(--space-4) var(--space-6)',
        width: '100%',
        zIndex: 'var(--z-emergency)',
        boxSizing: 'border-box',
      }}
    >
      {/* Icon + text — never colour alone */}
      <span aria-hidden="true" style={{ fontSize: '20px', marginRight: '8px' }}>⚠</span>
      <strong style={{ fontSize: 'var(--text-critical)' }}>
        Critical Finding — Immediate Review Required
      </strong>

      <p style={{ marginTop: 'var(--space-2)', marginBottom: 'var(--space-4)' }}>
        {finding}
      </p>

      {!acknowledgedAt ? (
        <button
          onClick={handleAcknowledge}
          style={{
            background: '#ffffff',
            color: 'var(--color-emergency)',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            padding: '0 var(--space-4)',
            minHeight: 'var(--min-tap-target)',
            fontWeight: 'bold',
            cursor: 'pointer',
          }}
          aria-label="Acknowledge this critical finding"
        >
          Acknowledge Critical Finding
        </button>
      ) : (
        <p style={{ fontSize: 'var(--text-label)', margin: 0 }}>
          Acknowledged at {new Date(acknowledgedAt).toLocaleString()}
        </p>
      )}
    </div>
  );
}
