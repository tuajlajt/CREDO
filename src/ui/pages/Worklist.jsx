/**
 * Worklist — Clinical patient queue with AI findings overview.
 *
 * Shows: patient queue, active study, AI report draft (amber-bordered card),
 * persistent critical finding banner (if any), sign & finalise actions.
 *
 * Owner agent: ui-designer-agent
 */

import React, { useState } from 'react';
import { AIOutputCard } from '../components/AIOutputCard';
import { CriticalAlert } from '../components/CriticalAlert';

export function Worklist() {
  // TODO: connect to API — GET /radiology/reports and GET /health
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [criticalFindings, setCriticalFindings] = useState([]);
  const [acknowledgedFindings, setAcknowledgedFindings] = useState({});

  const handleAcknowledge = (findingId, timestamp) => {
    setAcknowledgedFindings(prev => ({ ...prev, [findingId]: timestamp }));
    // TODO: POST acknowledgement to audit log API
  };

  return (
    <div style={{ fontFamily: 'var(--font-clinical)' }}>
      {/* Critical finding banner — persistent, always visible */}
      {criticalFindings.map(finding => (
        <CriticalAlert
          key={finding.id}
          finding={finding.description}
          onAcknowledge={(ts) => handleAcknowledge(finding.id, ts)}
          acknowledgedAt={acknowledgedFindings[finding.id]}
        />
      ))}

      {/* Main layout */}
      <div style={{ display: 'flex', height: 'calc(100vh - 60px)' }}>
        {/* Patient queue sidebar */}
        <aside style={{ width: '240px', borderRight: '1px solid #e5e7eb', padding: 'var(--space-4)' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 600 }}>Patient Queue</h2>
          {/* TODO: render patient list from API */}
          <p style={{ color: '#6b7280', fontSize: 'var(--text-label)' }}>Loading...</p>
        </aside>

        {/* Main study view */}
        <main style={{ flex: 1, padding: 'var(--space-6)' }}>
          {selectedPatient ? (
            <AIOutputCard
              title="Radiology Report Draft"
              confidence={0.0}
              content={<p>Select a patient to view AI report draft.</p>}
              onAcknowledge={() => {}}
            />
          ) : (
            <p style={{ color: '#6b7280' }}>Select a patient from the queue.</p>
          )}
        </main>
      </div>
    </div>
  );
}
