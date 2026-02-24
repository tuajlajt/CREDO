/**
 * ConfidenceIndicator — Display AI confidence as a labelled indicator.
 *
 * RULES:
 * - Never show raw float values (e.g., "0.73") without interpretation
 * - Always pair colour with text label (colour-blind accessibility)
 * - Low confidence must be clearly flagged — never suppress it
 *
 * Owner agent: ui-designer-agent
 */

import React from 'react';

/**
 * @param {object} props
 * @param {number} props.value - Confidence value 0.0 to 1.0
 */
export function ConfidenceIndicator({ value }) {
  const { label, colorClass } = getConfidenceInfo(value);

  return (
    <span
      className={`confidence confidence--${colorClass}`}
      aria-label={label}
      style={{ marginLeft: '8px', fontSize: 'var(--text-label)' }}
    >
      {/* Icon + text — never colour alone */}
      <ConfidenceIcon level={colorClass} aria-hidden="true" />
      {' '}{label}
    </span>
  );
}

function getConfidenceInfo(value) {
  if (value >= 0.85) {
    return { label: 'High confidence', colorClass: 'high' };
  }
  if (value >= 0.65) {
    return { label: 'Moderate confidence', colorClass: 'moderate' };
  }
  return { label: 'Low confidence — review carefully', colorClass: 'low' };
}

function ConfidenceIcon({ level }) {
  // TODO: replace with actual icon component (e.g., heroicons, lucide)
  const icons = { high: '✓', moderate: '~', low: '!' };
  return <span aria-hidden="true">{icons[level] ?? '?'}</span>;
}
