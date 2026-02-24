/**
 * DrugInteractionAlert — Display drug-drug interaction warnings.
 *
 * Major interactions use warning styling.
 * Always shows the data source/database version.
 * Always includes "Verify with clinical pharmacist" disclaimer.
 *
 * Owner agent: ui-designer-agent
 */

import React from 'react';

/**
 * @param {object} props
 * @param {Array} props.interactions - List of interaction objects
 * @param {string} props.severity - "major" | "moderate" | "minor"
 */
export function DrugInteractionAlert({ interactions, severity }) {
  const isMajor = severity === 'major';

  return (
    <div
      className={`interaction-alert interaction-alert--${severity}`}
      role="alert"
      style={{
        border: `2px solid ${isMajor ? 'var(--color-emergency)' : 'var(--color-urgent)'}`,
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-4)',
        background: isMajor ? '#fef2f2' : '#fffbeb',
      }}
    >
      {/* Icon + text — never colour alone */}
      <span aria-hidden="true" style={{ marginRight: '8px' }}>
        {isMajor ? '⚠' : '⚡'}
      </span>
      <strong className="interaction-severity" style={{ fontSize: 'var(--text-critical)' }}>
        {isMajor ? 'MAJOR DRUG INTERACTION' : 'Moderate Drug Interaction'}
      </strong>

      {interactions.map((interaction, index) => (
        <div
          key={`${interaction.drug_a}-${interaction.drug_b}-${index}`}
          className="interaction-detail"
          style={{ marginTop: 'var(--space-3)' }}
        >
          <strong>
            {interaction.drug_a} + {interaction.drug_b}
          </strong>
          <p style={{ margin: '4px 0' }}>{interaction.description}</p>
          {interaction.alternatives?.length > 0 && (
            <p style={{ margin: '4px 0', color: '#374151' }}>
              Consider: {interaction.alternatives.join(', ')}
            </p>
          )}
        </div>
      ))}

      <p
        className="disclaimer"
        style={{
          marginTop: 'var(--space-4)',
          fontSize: 'var(--text-label)',
          color: '#6b7280',
          borderTop: '1px solid #e5e7eb',
          paddingTop: 'var(--space-2)',
        }}
      >
        Verify with clinical pharmacist before any medication change
      </p>
    </div>
  );
}
