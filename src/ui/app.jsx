import React, { useState, useEffect, useRef } from 'react';
import {
  Users, Calendar, Activity, FileText, Pill,
  Settings, Search, Plus, Mic, MicOff,
  Upload, Image as ImageIcon, File, X, ChevronRight,
  Stethoscope, Clock, AlertCircle, CheckCircle2, Shield, Loader2,
  ClipboardList, FlaskConical, ChevronDown,
  Heart, Wind, BookUser, Cigarette, Dumbbell, GlassWater,
  Salad, ChevronUp
} from 'lucide-react';
import { LAB_PANEL_GROUPS, IMAGING_MODALITIES, NO_BODY_PART_MODALITIES, COMMON_BODY_PARTS, IMAGING_CPT_LOOKUP, VISIT_TYPES } from './constants.js';

// Capitalise the sex_at_birth value from the DB (stored as 'male', 'female', etc.)
const capitalizeSex = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : '—';

// ── Vitals helpers ─────────────────────────────────────────────────────────────

function calcBmi(weightKg, heightCm) {
  if (!weightKg || !heightCm) return null;
  const h = heightCm / 100;
  return weightKg / (h * h);
}

function bmiCategory(bmi) {
  if (bmi == null) return null;
  if (bmi < 18.5) return { label: 'Underweight', cls: 'text-blue-600 bg-blue-50' };
  if (bmi < 25.0) return { label: 'Normal',       cls: 'text-green-700 bg-green-50' };
  if (bmi < 30.0) return { label: 'Overweight',   cls: 'text-amber-600 bg-amber-50' };
  return             { label: 'Obese',         cls: 'text-red-600   bg-red-50'   };
}

function hrCategory(bpm) {
  if (bpm == null) return null;
  if (bpm < 40)  return { label: 'Severe Bradycardia', cls: 'text-red-700 bg-red-100' };
  if (bpm < 60)  return { label: 'Bradycardia',         cls: 'text-amber-600 bg-amber-50' };
  if (bpm <= 100) return { label: 'Normal',              cls: 'text-green-700 bg-green-50' };
  if (bpm <= 120) return { label: 'Tachycardia',         cls: 'text-amber-600 bg-amber-50' };
  return             { label: 'Severe Tachycardia',  cls: 'text-red-700 bg-red-100' };
}

function spo2Category(pct) {
  if (pct == null) return null;
  if (pct >= 95) return { label: 'Normal',      cls: 'text-green-700 bg-green-50' };
  if (pct >= 90) return { label: 'Low',         cls: 'text-amber-600 bg-amber-50' };
  return            { label: 'Critical',     cls: 'text-red-700 bg-red-100' };
}

function bpCategory(systolic, diastolic) {
  if (!systolic || !diastolic) return null;
  if (systolic > 180 || diastolic > 120) return { label: 'Hypertensive Crisis', cls: 'text-red-700   bg-red-100'    };
  if (systolic >= 140 || diastolic >= 90) return { label: 'Stage 2 HTN',         cls: 'text-red-600   bg-red-50'     };
  if (systolic >= 130 || diastolic >= 80) return { label: 'Stage 1 HTN',         cls: 'text-orange-600 bg-orange-50' };
  if (systolic >= 120 && diastolic < 80)  return { label: 'Elevated',             cls: 'text-amber-600 bg-amber-50'  };
  return                                           { label: 'Normal',              cls: 'text-green-700 bg-green-50'  };
}

// Returns { direction:'up'|'down', color:'green'|'red'|'gray', pct:number } | null.
// Uses a 3-month window if ≥2 weight measurements exist there, else expands to 6 months.
// Arrow only shows when change is ≥ 10%.
function calcWeightTrend(weightHistory, heightCm) {
  if (!heightCm || !weightHistory || weightHistory.length < 2) return null;
  const now        = new Date();
  const threeMoAgo = new Date(now.getTime() - 90  * 86400000);
  const sixMoAgo   = new Date(now.getTime() - 180 * 86400000);

  const in3m = weightHistory.filter(w => new Date(w.measured_at) >= threeMoAgo);
  const win  = in3m.length >= 2
    ? in3m
    : weightHistory.filter(w => new Date(w.measured_at) >= sixMoAgo);
  if (win.length < 2) return null;

  // weightHistory (and win) sorted newest-first
  const oldKg = win[win.length - 1].weight_kg;
  const newKg = win[0].weight_kg;
  const pct   = (newKg - oldKg) / oldKg;
  if (Math.abs(pct) < 0.10) return null;

  const h      = heightCm / 100;
  const oldBmi = oldKg / (h * h);
  const newBmi = newKg / (h * h);

  const NORM_LO = 18.5, NORM_HI = 24.9;
  const bothNormal = oldBmi >= NORM_LO && oldBmi <= NORM_HI &&
                     newBmi >= NORM_LO && newBmi <= NORM_HI;
  let color;
  if (bothNormal) {
    color = 'gray';
  } else {
    const dist = b => b < NORM_LO ? NORM_LO - b : b > NORM_HI ? b - NORM_HI : 0;
    color = dist(newBmi) < dist(oldBmi) ? 'green' : 'red';
  }
  return { direction: pct > 0 ? 'up' : 'down', color, pct };
}

// --- MAIN COMPONENT ---
export default function App() {
  const [patients, setPatients] = useState([]);          // worklist rows from /ehr/worklist
  const [patientsLoading, setPatientsLoading] = useState(true);
  const [patientsError, setPatientsError] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedPatient, setSelectedPatient] = useState(null); // worklist row
  const [isLoggingVisit, setIsLoggingVisit] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  // Optimistic local visits added via NewVisitLog (not persisted to DB until write API exists)
  const [localVisitsByPatient, setLocalVisitsByPatient] = useState({});

  // Load patient worklist once on mount
  useEffect(() => {
    fetch('/ehr/worklist')
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(data => { setPatients(data); setPatientsLoading(false); })
      .catch(() => { setPatientsError('Could not load patient list. Is the server running?'); setPatientsLoading(false); });
  }, []);

  const viewPatient = (patient) => {
    setSelectedPatient(patient);
    setActiveTab('patient_detail');
    setIsLoggingVisit(false);
  };

  const closePatient = () => {
    setSelectedPatient(null);
    setActiveTab('dashboard');
    setIsLoggingVisit(false);
  };

  const handleSaveVisit = (patientId, newVisit) => {
    setLocalVisitsByPatient(prev => ({
      ...prev,
      [patientId]: [newVisit, ...(prev[patientId] || [])]
    }));
    setIsLoggingVisit(false);
  };

  // Client-side filter on the already-loaded worklist
  const filteredPatients = patients.filter(p =>
    (p.full_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (p.patient_id || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 font-sans overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col">
        <div className="h-16 flex items-center px-6 border-b border-slate-800 bg-slate-950">
          <Stethoscope className="w-6 h-6 text-blue-400 mr-3" />
          <span className="text-lg font-bold text-white tracking-wide">CREDO</span>
        </div>

        <nav className="flex-1 py-6 space-y-1">
          <button
            onClick={() => { setActiveTab('dashboard'); setSelectedPatient(null); setIsLoggingVisit(false); }}
            className={`w-full flex items-center px-6 py-3 transition-colors ${activeTab === 'dashboard' ? 'bg-blue-600/10 text-blue-400 border-r-4 border-blue-400' : 'hover:bg-slate-800 hover:text-white'}`}
          >
            <Users className="w-5 h-5 mr-3" /> Patients
          </button>
          <button className="w-full flex items-center px-6 py-3 hover:bg-slate-800 hover:text-white transition-colors">
            <Calendar className="w-5 h-5 mr-3" /> Appointments
          </button>
          <button className="w-full flex items-center px-6 py-3 hover:bg-slate-800 hover:text-white transition-colors">
            <Activity className="w-5 h-5 mr-3" /> Analytics
          </button>
          <button className="w-full flex items-center px-6 py-3 hover:bg-slate-800 hover:text-white transition-colors">
            <Settings className="w-5 h-5 mr-3" /> Settings
          </button>
        </nav>

        <div className="p-6 border-t border-slate-800 flex items-center">
          <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-white font-bold mr-3">
            TK
          </div>
          <div>
            <p className="text-sm font-medium text-white">Dr. Tara Knowles</p>
            <p className="text-xs text-slate-500">Primary Care Physician</p>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 z-10">
          <div className="flex items-center text-slate-500 text-sm">
            {activeTab === 'dashboard' ? (
              <span className="font-medium text-slate-800">Patient Directory</span>
            ) : (
              <>
                <button onClick={closePatient} className="hover:text-blue-600 font-medium transition-colors">Patient Directory</button>
                <ChevronRight className="w-4 h-4 mx-2" />
                <span className="font-medium text-slate-800">{selectedPatient?.full_name}</span>
                {isLoggingVisit && (
                  <>
                    <ChevronRight className="w-4 h-4 mx-2" />
                    <span className="font-medium text-blue-600">New Visit Log</span>
                  </>
                )}
              </>
            )}
          </div>

          <div className="flex items-center space-x-4">
            <button className="p-2 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition-colors">
              <AlertCircle className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Dynamic Content */}
        <div className="flex-1 overflow-y-auto p-8 bg-slate-50/50">
          {activeTab === 'dashboard' && (
            <div className="max-w-6xl mx-auto space-y-6">
              <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold text-slate-800">My Patients</h1>
                <div className="relative">
                  <Search className="w-5 h-5 text-slate-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search patients by name or ID..."
                    className="pl-10 pr-4 py-2 border border-slate-300 rounded-lg w-80 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                {patientsLoading ? (
                  <div className="flex items-center justify-center py-16 text-slate-500">
                    <div className="text-center">
                      <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                      <p>Loading patients...</p>
                    </div>
                  </div>
                ) : patientsError ? (
                  <div className="py-16 text-center text-red-600">
                    <AlertCircle className="w-8 h-8 mx-auto mb-2" />
                    <p>{patientsError}</p>
                  </div>
                ) : (
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-sm">
                        <th className="px-6 py-4 font-medium">Patient ID</th>
                        <th className="px-6 py-4 font-medium">Name</th>
                        <th className="px-6 py-4 font-medium">Age / Gender</th>
                        <th className="px-6 py-4 font-medium">Last Visit</th>
                        <th className="px-6 py-4 font-medium text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredPatients.map(patient => (
                        <tr
                          key={patient.patient_id}
                          className="hover:bg-slate-50 transition-colors group cursor-pointer"
                          onClick={() => viewPatient(patient)}
                        >
                          <td className="px-6 py-4 text-sm font-medium text-blue-600">{patient.patient_id}</td>
                          <td className="px-6 py-4 font-medium text-slate-800">{patient.full_name}</td>
                          <td className="px-6 py-4 text-sm text-slate-600">
                            {patient.age} y/o • {capitalizeSex(patient.sex_at_birth)}
                          </td>
                          <td className="px-6 py-4 text-sm text-slate-600">
                            {patient.last_visit_date || 'No visits'}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <button className="text-sm font-medium text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity">
                              View EHR
                            </button>
                          </td>
                        </tr>
                      ))}
                      {filteredPatients.length === 0 && !patientsLoading && (
                        <tr>
                          <td colSpan="5" className="px-6 py-8 text-center text-slate-500">
                            No patients found matching your search.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {activeTab === 'patient_detail' && !isLoggingVisit && selectedPatient && (
            <PatientEHR
              patientId={selectedPatient.patient_id}
              extraVisits={localVisitsByPatient[selectedPatient.patient_id] || []}
              onNewVisit={() => setIsLoggingVisit(true)}
            />
          )}

          {activeTab === 'patient_detail' && isLoggingVisit && selectedPatient && (
            <NewVisitLog
              patient={selectedPatient}
              onCancel={() => setIsLoggingVisit(false)}
              onSave={(visitData) => handleSaveVisit(selectedPatient.patient_id, visitData)}
            />
          )}
        </div>
      </main>
    </div>
  );
}

// --- SUBCOMPONENTS ---

function PatientEHR({ patientId, extraVisits = [], onNewVisit }) {
  const [profile, setProfile] = useState(null);
  const [visits, setVisits] = useState([]);
  const [medications, setMedications] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [vitals, setVitals] = useState({ weight_history: [], bp_history: [], hr_history: [], spo2_history: [] });
  const [background, setBackground] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [innerTab, setInnerTab] = useState('history');
  const [vitalsExpanded, setVitalsExpanded] = useState({});

  // Fetch all six data slices in parallel whenever the patient changes
  useEffect(() => {
    setLoading(true);
    setError(null);
    setInnerTab('history');
    setVitalsExpanded({});
    Promise.all([
      fetch(`/ehr/patients/${patientId}/profile`).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); }),
      fetch(`/ehr/patients/${patientId}/visits`).then(r => r.json()),
      fetch(`/ehr/patients/${patientId}/medications`).then(r => r.json()),
      fetch(`/ehr/patients/${patientId}/documents`).then(r => r.json()),
      fetch(`/ehr/patients/${patientId}/vitals`).then(r => r.json()),
      fetch(`/ehr/patients/${patientId}/background`).then(r => r.ok ? r.json() : null),
    ])
      .then(([prof, vis, meds, docs, vit, bg]) => {
        setProfile(prof);
        setVisits(vis);
        setMedications(meds);
        setDocuments(docs);
        setVitals(vit);
        setBackground(bg);
        setLoading(false);
      })
      .catch(() => { setError('Failed to load patient data.'); setLoading(false); });
  }, [patientId]);

  if (loading) return (
    <div className="max-w-6xl mx-auto flex items-center justify-center h-64">
      <div className="text-slate-500 text-center">
        <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <p>Loading patient record...</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="max-w-6xl mx-auto flex items-center justify-center h-64 text-red-600">
      <div className="text-center">
        <AlertCircle className="w-8 h-8 mx-auto mb-2" />
        <p>{error}</p>
      </div>
    </div>
  );

  if (!profile) return null;

  const fullName = `${profile.given_names} ${profile.family_name}`;
  const initials = fullName.trim().split(/\s+/).map(n => n[0]).join('').toUpperCase().slice(0, 2);
  const gender = capitalizeSex(profile.sex_at_birth);

  // Merge any locally-added (optimistic) visits in front of the fetched ones
  const allVisits = [...extraVisits, ...visits];

  // Vitals quick stats (used in header card and vitals tab)
  const lastWeight = vitals.weight_history[0] || null;
  const lastBp     = vitals.bp_history[0]     || null;
  const bmiVal     = calcBmi(lastWeight?.weight_kg, profile.height_cm);
  const bmiCat     = bmiCategory(bmiVal);
  const trend      = calcWeightTrend(vitals.weight_history, profile.height_cm);
  const trendArrowStyle = trend
    ? trend.color === 'green' ? 'text-green-500' : trend.color === 'red' ? 'text-red-500' : 'text-slate-400'
    : '';
  const trendArrow = trend ? (trend.direction === 'up' ? '↑' : '↓') : null;

  // Split medications: chronic therapy = current; everything else = history
  const currentMeds = medications.filter(m => m.therapy_type === 'chronic');
  const historyMeds  = medications.filter(m => m.therapy_type !== 'chronic');

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Patient Header Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex justify-between items-start">
          <div className="flex items-center space-x-6">
            <div className="w-20 h-20 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 text-2xl font-bold">
              {initials}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-800 flex items-center">
                {fullName}
                <span className="ml-3 text-sm font-normal text-slate-500 bg-slate-100 px-2 py-1 rounded">
                  {profile.patient_id}
                </span>
              </h1>
              <div className="mt-2 text-sm text-slate-600 flex space-x-4">
                <span><strong className="text-slate-800">Age:</strong> {profile.age ?? '—'}</span>
                <span><strong className="text-slate-800">Gender:</strong> {gender}</span>
                <span><strong className="text-slate-800">Blood:</strong> {profile.blood_type || '—'}</span>
              </div>
              <div className="mt-1 text-sm text-slate-600 flex space-x-4">
                <span><strong className="text-slate-800">Phone:</strong> {profile.phone || '—'}</span>
                <span><strong className="text-slate-800">Email:</strong> {profile.email || '—'}</span>
              </div>
              {(lastWeight || lastBp) && (
                <div className="mt-2 flex items-center gap-5 text-sm">
                  {lastWeight && (
                    <span className="flex items-center gap-1 text-slate-600">
                      <strong className="text-slate-800">Weight:</strong>
                      {lastWeight.weight_kg} kg
                      {trendArrow && (
                        <span className={`font-bold text-base leading-none ${trendArrowStyle}`} title={`${Math.abs(trend.pct * 100).toFixed(1)}% over last 3–6 months`}>
                          {trendArrow}
                        </span>
                      )}
                    </span>
                  )}
                  {bmiVal && bmiCat && (
                    <span className="flex items-center gap-1 text-slate-600">
                      <strong className="text-slate-800">BMI:</strong>
                      {bmiVal.toFixed(1)}
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${bmiCat.cls}`}>{bmiCat.label}</span>
                    </span>
                  )}
                  {lastBp && (
                    <span className="flex items-center gap-1 text-slate-600">
                      <strong className="text-slate-800">BP:</strong>
                      {lastBp.systolic_mmhg}/{lastBp.diastolic_mmhg} mmHg
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
          <button
            onClick={onNewVisit}
            className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4 mr-2" /> Log New Visit
          </button>
        </div>

        <div className="mt-6 pt-6 border-t border-slate-100 grid grid-cols-2 gap-6">
          <div className="bg-red-50/50 p-4 rounded-lg border border-red-100">
            <h3 className="text-sm font-bold text-red-800 mb-2 flex items-center">
              <AlertCircle className="w-4 h-4 mr-1" /> Allergies
            </h3>
            <div className="flex flex-wrap gap-2">
              {profile.allergies.length > 0
                ? profile.allergies.map((a, i) => (
                    <span key={i} className="px-2 py-1 bg-red-100 text-red-700 text-xs font-medium rounded-md">
                      {a.substance}
                    </span>
                  ))
                : <span className="text-xs text-slate-400">None recorded</span>
              }
            </div>
          </div>
          <div className="bg-amber-50/50 p-4 rounded-lg border border-amber-100">
            <h3 className="text-sm font-bold text-amber-800 mb-2 flex items-center">
              <Activity className="w-4 h-4 mr-1" /> Chronic Conditions
            </h3>
            <div className="flex flex-wrap gap-2">
              {profile.conditions.length > 0
                ? profile.conditions.map((c, i) => (
                    <span key={i} className="px-2 py-1 bg-amber-100 text-amber-800 text-xs font-medium rounded-md">
                      {c.display}
                    </span>
                  ))
                : <span className="text-xs text-slate-400">None recorded</span>
              }
            </div>
          </div>
        </div>
      </div>

      {/* Detail Tabs */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="flex border-b border-slate-200">
          {[
            { id: 'history',    label: 'Visit History',      icon: Clock },
            { id: 'meds',       label: 'Medications',         icon: Pill },
            { id: 'vitals',     label: 'Vitals',               icon: Activity },
            { id: 'labs',       label: 'Labs & Imaging',       icon: FileText },
            { id: 'background', label: 'Patient Background',   icon: BookUser },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setInnerTab(tab.id)}
              className={`flex-1 py-4 text-sm font-medium flex items-center justify-center border-b-2 transition-colors ${
                innerTab === tab.id
                  ? 'border-blue-600 text-blue-600 bg-blue-50/30'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              <tab.icon className="w-4 h-4 mr-2" /> {tab.label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {innerTab === 'history' && (
            <div className="space-y-6">
              {allVisits.map((visit, idx) => {
                // Support both locally-added visits (mock shape) and DB visits (API shape)
                const visitId       = visit.id                  || visit.visit_id;
                const visitDate     = visit.date                || visit.visit_date;
                const visitReason   = visit.reason              || visit.patient_reported_reason;
                const visitNotes    = visit.notes               || visit.clinician_notes;
                const visitDiagnosis =
                  visit.diagnosis ||
                  (visit.diagnoses || []).map(d => d.display).filter(Boolean).join('; ') ||
                  '—';
                const visitRx = (visit.prescriptions || []).map(p => ({
                  name:      p.name         || p.medicine_name,
                  dosage:    p.dosage       || p.dose,
                  frequency: p.frequency,
                }));

                return (
                  <div key={visitId || idx} className="relative pl-6 border-l-2 border-slate-200 pb-6 last:pb-0">
                    <div className="absolute w-3 h-3 bg-white border-2 border-blue-500 rounded-full -left-[7.5px] top-1"></div>
                    <div className="bg-slate-50 rounded-lg p-5 border border-slate-100">
                      <div className="flex justify-between items-start mb-3">
                        <div>
                          <h4 className="text-lg font-bold text-slate-800">{visitReason || '—'}</h4>
                          <span className="text-sm text-slate-500 font-medium">{visitDate}</span>
                        </div>
                        <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded font-medium">{visitId}</span>
                      </div>

                      <div className="mb-4">
                        <strong className="text-sm text-slate-700 block mb-1">Diagnosis:</strong>
                        <p className="text-sm text-slate-800 bg-white p-3 rounded border border-slate-200">{visitDiagnosis}</p>
                      </div>

                      <div className="mb-4">
                        <strong className="text-sm text-slate-700 block mb-1">Clinical Notes:</strong>
                        <p className="text-sm text-slate-600 leading-relaxed bg-white p-3 rounded border border-slate-200">{visitNotes || '—'}</p>
                      </div>

                      {visitRx.length > 0 && (
                        <div className="mt-4">
                          <strong className="text-sm text-slate-700 block mb-2 flex items-center">
                            <Pill className="w-4 h-4 mr-1 text-blue-500" /> Prescribed:
                          </strong>
                          <ul className="space-y-2">
                            {visitRx.map((p, i) => (
                              <li key={i} className="text-sm text-slate-700 bg-white p-2 rounded border border-slate-100 flex items-center justify-between">
                                <span className="font-medium text-slate-900">{p.name}</span>
                                <span className="text-slate-500">{p.dosage} — {p.frequency}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
              {allVisits.length === 0 && (
                <p className="text-slate-500 text-center py-8">No visit history recorded.</p>
              )}
            </div>
          )}

          {innerTab === 'meds' && (
            <div className="space-y-4">
              {medications.length === 0 && (
                <p className="text-slate-500 text-center py-8">No medications prescribed.</p>
              )}

              {/* Current medications (chronic therapy) */}
              {currentMeds.length > 0 && (
                <>
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-2">
                    <Pill className="w-3.5 h-3.5 text-blue-500" /> Current Medications
                  </h3>
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-sm">
                        <th className="px-4 py-3 font-medium">Medication</th>
                        <th className="px-4 py-3 font-medium">Dosage</th>
                        <th className="px-4 py-3 font-medium">Frequency</th>
                        <th className="px-4 py-3 font-medium">Prescribed Date</th>
                        <th className="px-4 py-3 font-medium">Visit Ref</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {currentMeds.map((m, i) => (
                        <tr key={m.prescription_id || i} className="hover:bg-slate-50">
                          <td className="px-4 py-3 text-sm font-medium text-slate-800">{m.medicine_name}</td>
                          <td className="px-4 py-3 text-sm text-slate-600">{m.dose}</td>
                          <td className="px-4 py-3 text-sm text-slate-600">{m.frequency}</td>
                          <td className="px-4 py-3 text-sm text-slate-600">{m.prescribed_date}</td>
                          <td className="px-4 py-3 text-sm text-blue-600">{m.visit_ref_id || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}

              {/* Divider between current and history */}
              {currentMeds.length > 0 && historyMeds.length > 0 && (
                <div className="flex items-center gap-3 py-1">
                  <div className="flex-1 border-t border-slate-200" />
                  <span className="text-xs text-slate-400 uppercase tracking-wider font-medium">Medication History</span>
                  <div className="flex-1 border-t border-slate-200" />
                </div>
              )}

              {/* Medication history (acute / unknown / other) */}
              {historyMeds.length > 0 && (
                <>
                  {currentMeds.length === 0 && (
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-2">
                      <Pill className="w-3.5 h-3.5 text-slate-400" /> Medication History
                    </h3>
                  )}
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-sm">
                        <th className="px-4 py-3 font-medium">Medication</th>
                        <th className="px-4 py-3 font-medium">Dosage</th>
                        <th className="px-4 py-3 font-medium">Frequency</th>
                        <th className="px-4 py-3 font-medium">Prescribed Date</th>
                        <th className="px-4 py-3 font-medium">Visit Ref</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {historyMeds.map((m, i) => (
                        <tr key={m.prescription_id || i} className="hover:bg-slate-50 text-slate-500">
                          <td className="px-4 py-3 text-sm font-medium">{m.medicine_name}</td>
                          <td className="px-4 py-3 text-sm">{m.dose}</td>
                          <td className="px-4 py-3 text-sm">{m.frequency}</td>
                          <td className="px-4 py-3 text-sm">{m.prescribed_date}</td>
                          <td className="px-4 py-3 text-sm text-blue-500">{m.visit_ref_id || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          )}

          {innerTab === 'vitals' && (() => {
            const PAGE = 5;
            const toggleExpand = (key) =>
              setVitalsExpanded(prev => ({ ...prev, [key]: !prev[key] }));
            const visibleRows = (key, arr) =>
              vitalsExpanded[key] ? arr : arr.slice(0, PAGE);
            const expandBtn = (key, arr) => arr.length > PAGE && (
              <button
                type="button"
                onClick={() => toggleExpand(key)}
                className="mt-2 text-xs text-blue-500 hover:text-blue-700 flex items-center gap-1"
              >
                {vitalsExpanded[key]
                  ? <><ChevronUp className="w-3 h-3" /> Show less</>
                  : <><ChevronDown className="w-3 h-3" /> Show {arr.length - PAGE} more</>}
              </button>
            );

            // Static summary row — always visible even without measurements
            const latestWeight = vitals.weight_history[0];
            const latestBp     = vitals.bp_history[0];
            const latestHr     = vitals.hr_history[0];
            const latestSpo2   = vitals.spo2_history[0];
            const latestBmi    = latestWeight ? calcBmi(latestWeight.weight_kg, profile.height_cm) : null;
            const bmiCat       = bmiCategory(latestBmi);

            return (
            <div className="space-y-8">

              {/* ── Static summary bar ─────────────────────────────────────────── */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {/* Height */}
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Height</p>
                  <p className="text-2xl font-bold text-slate-800">
                    {profile.height_cm ? `${profile.height_cm}` : '—'}
                    {profile.height_cm && <span className="text-sm font-normal text-slate-500 ml-1">cm</span>}
                  </p>
                </div>
                {/* Weight (latest) */}
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Weight</p>
                  <p className="text-2xl font-bold text-slate-800">
                    {latestWeight ? `${latestWeight.weight_kg}` : '—'}
                    {latestWeight && <span className="text-sm font-normal text-slate-500 ml-1">kg</span>}
                  </p>
                  {bmiCat && (
                    <span className={`mt-1 inline-block text-xs font-medium px-2 py-0.5 rounded ${bmiCat.cls}`}>
                      BMI {latestBmi.toFixed(1)} · {bmiCat.label}
                    </span>
                  )}
                </div>
                {/* Blood pressure (latest) */}
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Blood Pressure</p>
                  <p className="text-2xl font-bold text-slate-800">
                    {latestBp
                      ? <>{latestBp.systolic_mmhg}<span className="text-base font-normal text-slate-400">/{latestBp.diastolic_mmhg}</span></>
                      : '—'}
                    {latestBp && <span className="text-sm font-normal text-slate-500 ml-1">mmHg</span>}
                  </p>
                  {latestBp && (() => { const c = bpCategory(latestBp.systolic_mmhg, latestBp.diastolic_mmhg); return c ? <span className={`mt-1 inline-block text-xs font-medium px-2 py-0.5 rounded ${c.cls}`}>{c.label}</span> : null; })()}
                </div>
                {/* Heart rate (latest) */}
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Heart Rate</p>
                  <p className="text-2xl font-bold text-slate-800">
                    {latestHr ? `${latestHr.heart_rate_bpm}` : '—'}
                    {latestHr && <span className="text-sm font-normal text-slate-500 ml-1">bpm</span>}
                  </p>
                  {latestHr && (() => { const c = hrCategory(Number(latestHr.heart_rate_bpm)); return c ? <span className={`mt-1 inline-block text-xs font-medium px-2 py-0.5 rounded ${c.cls}`}>{c.label}</span> : null; })()}
                </div>
                {/* SpO2 (latest) */}
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">SpO₂</p>
                  <p className="text-2xl font-bold text-slate-800">
                    {latestSpo2 ? `${latestSpo2.spo2_pct}` : '—'}
                    {latestSpo2 && <span className="text-sm font-normal text-slate-500 ml-1">%</span>}
                  </p>
                  {latestSpo2 && (() => { const c = spo2Category(Number(latestSpo2.spo2_pct)); return c ? <span className={`mt-1 inline-block text-xs font-medium px-2 py-0.5 rounded ${c.cls}`}>{c.label}</span> : null; })()}
                </div>
              </div>

              {/* ── Weight history ──────────────────────────────────────────────── */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-blue-500" /> Weight History
                </h3>
                {vitals.weight_history.length > 0 ? (
                  <>
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-sm">
                        <th className="px-4 py-3 font-medium">Date</th>
                        <th className="px-4 py-3 font-medium">Weight (kg)</th>
                        <th className="px-4 py-3 font-medium">BMI</th>
                        <th className="px-4 py-3 font-medium">Category</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {visibleRows('weight', vitals.weight_history).map((w, i) => {
                        const rowBmi = calcBmi(w.weight_kg, profile.height_cm);
                        const rowCat = bmiCategory(rowBmi);
                        const isLatest = i === 0;
                        return (
                          <tr key={w.vital_id || i} className={isLatest ? 'bg-blue-50/40' : 'hover:bg-slate-50'}>
                            <td className="px-4 py-3 text-sm text-slate-700">
                              {(w.measured_at || '').split('T')[0]}
                              {isLatest && <span className="ml-2 text-xs text-blue-500 font-medium">latest</span>}
                            </td>
                            <td className="px-4 py-3 text-sm font-medium text-slate-800">
                              {w.weight_kg} kg
                              {isLatest && trendArrow && (
                                <span className={`ml-1 font-bold ${trendArrowStyle}`} title={`${Math.abs(trend.pct * 100).toFixed(1)}% change`}>
                                  {trendArrow}
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-sm text-slate-600">
                              {rowBmi ? rowBmi.toFixed(1) : '—'}
                            </td>
                            <td className="px-4 py-3 text-sm">
                              {rowCat
                                ? <span className={`text-xs font-medium px-2 py-0.5 rounded ${rowCat.cls}`}>{rowCat.label}</span>
                                : '—'
                              }
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {expandBtn('weight', vitals.weight_history)}
                  </>
                ) : (
                  <p className="text-sm text-slate-400 italic">No weight measurements recorded.</p>
                )}
              </div>

              {/* ── Blood pressure history ──────────────────────────────────────── */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-rose-500" /> Blood Pressure History
                </h3>
                {vitals.bp_history.length > 0 ? (
                  <>
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-sm">
                        <th className="px-4 py-3 font-medium">Date</th>
                        <th className="px-4 py-3 font-medium">Systolic</th>
                        <th className="px-4 py-3 font-medium">Diastolic</th>
                        <th className="px-4 py-3 font-medium">Category</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {visibleRows('bp', vitals.bp_history).map((bp, i) => {
                        const cat = bpCategory(bp.systolic_mmhg, bp.diastolic_mmhg);
                        const isLatest = i === 0;
                        return (
                          <tr key={bp.vital_id || i} className={isLatest ? 'bg-blue-50/40' : 'hover:bg-slate-50'}>
                            <td className="px-4 py-3 text-sm text-slate-700">
                              {(bp.measured_at || '').split('T')[0]}
                              {isLatest && <span className="ml-2 text-xs text-blue-500 font-medium">latest</span>}
                            </td>
                            <td className="px-4 py-3 text-sm font-medium text-slate-800">{bp.systolic_mmhg}</td>
                            <td className="px-4 py-3 text-sm font-medium text-slate-800">{bp.diastolic_mmhg}</td>
                            <td className="px-4 py-3 text-sm">
                              {cat
                                ? <span className={`text-xs font-medium px-2 py-0.5 rounded ${cat.cls}`}>{cat.label}</span>
                                : '—'
                              }
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {expandBtn('bp', vitals.bp_history)}
                  </>
                ) : (
                  <p className="text-sm text-slate-400 italic">No blood pressure measurements recorded.</p>
                )}
              </div>

              {/* ── Heart rate history ──────────────────────────────────────────── */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                  <Heart className="w-4 h-4 text-pink-500" /> Heart Rate History
                </h3>
                {vitals.hr_history.length > 0 ? (
                  <>
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-sm">
                        <th className="px-4 py-3 font-medium">Date</th>
                        <th className="px-4 py-3 font-medium">Heart Rate</th>
                        <th className="px-4 py-3 font-medium">Category</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {visibleRows('hr', vitals.hr_history).map((hr, i) => {
                        const cat = hrCategory(Number(hr.heart_rate_bpm));
                        const isLatest = i === 0;
                        return (
                          <tr key={hr.vital_id || i} className={isLatest ? 'bg-blue-50/40' : 'hover:bg-slate-50'}>
                            <td className="px-4 py-3 text-sm text-slate-700">
                              {(hr.measured_at || '').split('T')[0]}
                              {isLatest && <span className="ml-2 text-xs text-blue-500 font-medium">latest</span>}
                            </td>
                            <td className="px-4 py-3 text-sm font-medium text-slate-800">{hr.heart_rate_bpm} bpm</td>
                            <td className="px-4 py-3 text-sm">
                              {cat
                                ? <span className={`text-xs font-medium px-2 py-0.5 rounded ${cat.cls}`}>{cat.label}</span>
                                : '—'
                              }
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {expandBtn('hr', vitals.hr_history)}
                  </>
                ) : (
                  <p className="text-sm text-slate-400 italic">No heart rate measurements recorded.</p>
                )}
              </div>

              {/* ── SpO2 history ────────────────────────────────────────────────── */}
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                  <Wind className="w-4 h-4 text-cyan-500" /> Oxygen Saturation (SpO₂)
                </h3>
                {vitals.spo2_history.length > 0 ? (
                  <>
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-sm">
                        <th className="px-4 py-3 font-medium">Date</th>
                        <th className="px-4 py-3 font-medium">SpO₂</th>
                        <th className="px-4 py-3 font-medium">Category</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {visibleRows('spo2', vitals.spo2_history).map((s, i) => {
                        const cat = spo2Category(Number(s.spo2_pct));
                        const isLatest = i === 0;
                        return (
                          <tr key={s.vital_id || i} className={isLatest ? 'bg-blue-50/40' : 'hover:bg-slate-50'}>
                            <td className="px-4 py-3 text-sm text-slate-700">
                              {(s.measured_at || '').split('T')[0]}
                              {isLatest && <span className="ml-2 text-xs text-blue-500 font-medium">latest</span>}
                            </td>
                            <td className="px-4 py-3 text-sm font-medium text-slate-800">{s.spo2_pct}%</td>
                            <td className="px-4 py-3 text-sm">
                              {cat
                                ? <span className={`text-xs font-medium px-2 py-0.5 rounded ${cat.cls}`}>{cat.label}</span>
                                : '—'
                              }
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {expandBtn('spo2', vitals.spo2_history)}
                  </>
                ) : (
                  <p className="text-sm text-slate-400 italic">No SpO₂ measurements recorded.</p>
                )}
              </div>

            </div>
            );
          })()}

          {innerTab === 'labs' && (() => {
            const pendingOrders  = documents.filter(d => d.source === 'order');
            const completedItems = documents.filter(d => d.source !== 'order');
            return (
              <div className="space-y-6">
                {/* Pending orders */}
                {pendingOrders.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                      <ClipboardList className="w-3.5 h-3.5 text-amber-500" />
                      Pending Orders ({pendingOrders.length})
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      {pendingOrders.map((doc, i) => (
                        <div key={i} className="border border-dashed border-amber-300 bg-amber-50/60 rounded-lg p-4">
                          <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center mb-3">
                            {doc.category === 'imaging'
                              ? <ImageIcon   className="w-5 h-5 text-blue-500" />
                              : <FlaskConical className="w-5 h-5 text-amber-600" />}
                          </div>
                          <h4 className="text-sm font-medium text-slate-800 truncate" title={doc.title}>
                            {doc.title}
                          </h4>
                          <div className="flex justify-between items-center mt-2">
                            <span className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-medium uppercase tracking-wide">
                              {doc.detail || 'requested'}
                            </span>
                            <span className="text-xs text-slate-400">{(doc.date || '').split('T')[0]}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Divider */}
                {pendingOrders.length > 0 && completedItems.length > 0 && (
                  <div className="flex items-center gap-3">
                    <div className="flex-1 border-t border-slate-200" />
                    <span className="text-xs text-slate-400 uppercase tracking-wider font-medium">Results &amp; Documents</span>
                    <div className="flex-1 border-t border-slate-200" />
                  </div>
                )}

                {/* Completed results / documents */}
                {completedItems.length > 0 && (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {completedItems.map((doc, i) => (
                      <div key={i} className="border border-slate-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-md transition-all group cursor-pointer bg-white">
                        <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center mb-3 group-hover:bg-blue-50">
                          {doc.category === 'imaging'
                            ? <ImageIcon className="w-6 h-6 text-blue-500" />
                            : <File      className="w-6 h-6 text-red-500"  />}
                        </div>
                        <h4 className="text-sm font-medium text-slate-800 truncate" title={doc.title}>
                          {doc.title}
                        </h4>
                        {doc.detail && (
                          <p className="text-xs text-slate-500 mt-1 truncate" title={doc.detail}>{doc.detail}</p>
                        )}
                        <div className="flex justify-between items-center mt-2">
                          <span className="text-xs text-slate-500 uppercase">{doc.category}</span>
                          <span className="text-xs text-slate-400">{(doc.date || '').split('T')[0]}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {documents.length === 0 && (
                  <div className="py-12 text-center text-slate-500 flex flex-col items-center">
                    <FileText className="w-12 h-12 text-slate-300 mb-3" />
                    <p>No lab tests, imaging, or orders found.</p>
                  </div>
                )}
              </div>
            );
          })()}

          {/* ── Patient Background tab ─────────────────────────────────────── */}
          {innerTab === 'background' && (() => {
            const ls = background?.lifestyle;
            const fh = background?.family_history || [];

            const smokingLabel = (s) => ({
              'no': 'Non-smoker',
              'never': 'Never smoked',
              'ex': 'Ex-smoker',
              'ex_smoker': 'Ex-smoker',
              'yes': 'Current smoker',
              'current': 'Current smoker',
              'occasional': 'Occasional smoker',
              'passive': 'Passive/second-hand exposure',
            })[s?.toLowerCase()] || s || '—';

            const smokingColor = (s) => {
              const low  = s?.toLowerCase();
              if (!low || low === 'no' || low === 'never') return 'text-green-700 bg-green-50';
              if (low === 'ex' || low === 'ex_smoker')     return 'text-amber-600 bg-amber-50';
              return 'text-red-700 bg-red-50';
            };

            const dietLabel = (d) => ({
              'balanced': 'Balanced',
              'mediterranean': 'Mediterranean',
              'low_carb': 'Low-carb',
              'western': 'Western / High-processed',
              'vegetarian': 'Vegetarian',
              'vegan': 'Vegan',
              'high_protein': 'High-protein',
              'unknown': '—',
            })[d?.toLowerCase()] || d || '—';

            return (
              <div className="space-y-8">
                {/* ── Lifestyle ──────────────────────────────────────────────── */}
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
                    <Dumbbell className="w-4 h-4 text-violet-500" /> Lifestyle
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {/* Smoking */}
                    <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
                      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
                        <Cigarette className="w-3.5 h-3.5" /> Smoking
                      </div>
                      {ls ? (
                        <span className={`text-xs font-medium px-2 py-1 rounded ${smokingColor(ls.smoking_status)}`}>
                          {smokingLabel(ls.smoking_status)}
                        </span>
                      ) : <p className="text-sm text-slate-400">—</p>}
                    </div>
                    {/* Diet */}
                    <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
                      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
                        <Salad className="w-3.5 h-3.5" /> Diet
                      </div>
                      <p className="text-sm font-medium text-slate-700">{ls ? dietLabel(ls.diet_pattern) : '—'}</p>
                    </div>
                    {/* Alcohol */}
                    <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
                      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
                        <GlassWater className="w-3.5 h-3.5" /> Alcohol
                      </div>
                      {ls?.alcohol_units_per_week != null
                        ? <p className="text-sm font-medium text-slate-700">{ls.alcohol_units_per_week} units/week</p>
                        : ls?.alcohol_units_per_month != null
                          ? <p className="text-sm font-medium text-slate-700">{ls.alcohol_units_per_month} units/month</p>
                          : <p className="text-sm text-slate-400">—</p>}
                    </div>
                    {/* Physical activity */}
                    <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
                      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
                        <Dumbbell className="w-3.5 h-3.5" /> Activity
                      </div>
                      {ls?.activity_sessions_per_week != null
                        ? <p className="text-sm font-medium text-slate-700">{ls.activity_sessions_per_week} sessions/week</p>
                        : <p className="text-sm text-slate-400">—</p>}
                    </div>
                  </div>
                </div>

                {/* ── Family History ──────────────────────────────────────────── */}
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
                    <Users className="w-4 h-4 text-indigo-500" /> Family History
                  </h3>
                  {fh.length > 0 ? (
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-sm">
                          <th className="px-4 py-3 font-medium">Relation</th>
                          <th className="px-4 py-3 font-medium">Condition</th>
                          <th className="px-4 py-3 font-medium">Code</th>
                          <th className="px-4 py-3 font-medium">Age of Onset</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {fh.map((f, i) => (
                          <tr key={i} className="hover:bg-slate-50">
                            <td className="px-4 py-3 text-sm font-medium text-slate-800 capitalize">
                              {f.relation?.replace(/_/g, ' ')}
                            </td>
                            <td className="px-4 py-3 text-sm text-slate-700">{f.display}</td>
                            <td className="px-4 py-3 text-xs text-slate-400 font-mono">{f.code || '—'}</td>
                            <td className="px-4 py-3 text-sm text-slate-600">
                              {f.age_of_onset != null ? `~${f.age_of_onset}y` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="text-sm text-slate-400 italic">No family history recorded.</p>
                  )}
                </div>

                {!background && (
                  <div className="py-12 text-center text-slate-400">
                    <BookUser className="w-10 h-10 mx-auto mb-3 text-slate-300" />
                    <p>No background information available.</p>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
}

function CotBlock({ agent, reasoning }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="px-4 py-2 bg-white">
      <button
        type="button"
        onClick={() => setOpen(x => !x)}
        className="flex items-center w-full text-left gap-2 group"
      >
        <ChevronDown
          className={`w-3.5 h-3.5 text-indigo-400 flex-shrink-0 transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
        />
        <span className="text-xs font-semibold text-indigo-700 group-hover:text-indigo-900">
          {agent}
        </span>
      </button>
      {open && (
        <p className="mt-1 ml-5 text-xs text-slate-600 whitespace-pre-wrap leading-relaxed">
          {reasoning || '(no reasoning captured)'}
        </p>
      )}
    </div>
  );
}

function NewVisitLog({ patient, onCancel, onSave }) {
  // ── Form fields (all editable, pre-filled by AI) ────────────────────────────
  const [reason, setReason] = useState('');
  const [diagnoses, setDiagnoses] = useState([]);  // [{code, display, code_system, status}]
  const [notes, setNotes] = useState('');

  // Manual diagnosis entry
  const [diagCode, setDiagCode] = useState('');
  const [diagDisplay, setDiagDisplay] = useState('');

  // Prescriptions
  const [prescriptions, setPrescriptions] = useState([]);
  const [medName, setMedName] = useState('');
  const [medDosage, setMedDosage] = useState('');
  const [medFreq, setMedFreq] = useState('');

  // Vitals (optional)
  const [vitalWeight, setVitalWeight] = useState('');
  const [vitalSystolic, setVitalSystolic] = useState('');
  const [vitalDiastolic, setVitalDiastolic] = useState('');
  const [vitalHr, setVitalHr] = useState('');
  const [vitalSpo2, setVitalSpo2] = useState('');
  const [vitalTime, setVitalTime] = useState(() => {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  });

  // Recording / AI processing
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [aiError, setAiError] = useState(null);
  const [cotLog, setCotLog] = useState([]);       // [{agent, reasoning}] from multi-agent pipeline
  const [cotExpanded, setCotExpanded] = useState(false);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  // Drug safety check
  const [safetyState, setSafetyState] = useState('idle'); // 'idle'|'loading'|'done'|'error'
  const [safetyResult, setSafetyResult] = useState(null);

  // Save
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  // File attachments
  const [attachments, setAttachments] = useState([]);
  const fileInputRef = useRef(null);

  const patientName = patient.full_name || patient.name;

  // Visit type
  const [visitType, setVisitType] = useState('outpatient');

  // Lab / imaging orders
  const [orders, setOrders] = useState([]);
  const [customLabName, setCustomLabName] = useState('');
  const [imgModality, setImgModality] = useState('X-Ray');
  const [imgBodyPart, setImgBodyPart] = useState('');
  const [ordersExpanded, setOrdersExpanded] = useState(false);

  // Reset safety check whenever the prescription list changes
  useEffect(() => {
    setSafetyState('idle');
    setSafetyResult(null);
  }, [prescriptions.length]);

  // ── Diagnosis helpers ───────────────────────────────────────────────────────
  const handleAddDiagnosis = () => {
    if (!diagDisplay.trim()) return;
    setDiagnoses(prev => [...prev, {
      code: diagCode.trim(),
      display: diagDisplay.trim(),
      code_system: 'ICD-10',
      status: 'provisional',
    }]);
    setDiagCode('');
    setDiagDisplay('');
  };

  const removeDiagnosis = (index) => setDiagnoses(d => d.filter((_, i) => i !== index));

  // ── Prescription helpers ────────────────────────────────────────────────────
  const handleAddPrescription = () => {
    if (!medName || !medDosage) return;
    setPrescriptions(prev => [...prev, {
      medicine_name: medName,
      dose: medDosage,
      frequency: medFreq || 'as_needed',
      inn: medName,
      route: 'oral',
      therapy_type: 'acute',
    }]);
    setMedName(''); setMedDosage(''); setMedFreq('');
  };

  const removePrescription = (index) => setPrescriptions(p => p.filter((_, i) => i !== index));

  // ── File attachment helpers ─────────────────────────────────────────────────
  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    setAttachments(prev => [...prev, ...files.map(f => ({
      name: f.name,
      type: f.type,
      category: f.type.includes('pdf') ? 'lab' : 'imaging',
      file: f,
    }))]);
  };

  const removeAttachment = (index) => setAttachments(a => a.filter((_, i) => i !== index));

  // ── Order helpers ────────────────────────────────────────────────────────────
  const handleAddLabPreset = (test) => {
    if (orders.some(o => o.test_display === test.display)) return;
    setOrders(prev => [...prev, {
      category: 'lab',
      test_display: test.display,
      test_code: test.code,
      test_code_system: 'LOINC',
      status: 'requested',
    }]);
  };

  const handleAddCustomLab = () => {
    const name = customLabName.trim();
    if (!name || orders.some(o => o.test_display === name)) return;
    setOrders(prev => [...prev, {
      category: 'lab',
      test_display: name,
      test_code: '',
      test_code_system: 'LOINC',
      status: 'requested',
    }]);
    setCustomLabName('');
  };

  const handleAddImagingOrder = () => {
    const noBodyPart = NO_BODY_PART_MODALITIES.has(imgModality);
    if (!noBodyPart && !imgBodyPart.trim()) return;
    const display = noBodyPart
      ? imgModality
      : `${imgModality} — ${imgBodyPart.trim()}`;
    if (orders.some(o => o.test_display === display)) return;
    const cptKey = noBodyPart ? `${imgModality}_` : `${imgModality}_${imgBodyPart.trim()}`;
    const cptCode = IMAGING_CPT_LOOKUP[cptKey] || '';
    setOrders(prev => [...prev, {
      category: 'imaging',
      test_display: display,
      test_code: cptCode,
      test_code_system: 'CPT',
      status: 'requested',
    }]);
    if (!noBodyPart) setImgBodyPart('');
  };

  const removeOrder = (index) => setOrders(o => o.filter((_, i) => i !== index));

  // ── MediaRecorder-based dictation ───────────────────────────────────────────
  const startRecording = async () => {
    setAiError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Use webm if supported, otherwise let the browser pick
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: mimeType || 'audio/webm' });
        await uploadAudioForAI(blob, mimeType);
      };

      recorder.start();
      setIsRecording(true);
    } catch (err) {
      setAiError('Microphone access denied. Please allow microphone access and try again.');
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
    setIsProcessing(true);
  };

  const uploadAudioForAI = async (blob, mimeType) => {
    try {
      const ext = mimeType && mimeType.includes('webm') ? 'webm' : 'wav';
      const formData = new FormData();
      formData.append('file', blob, `dictation.${ext}`);

      const response = await fetch(
        `/clinical/visit/${patient.patient_id}`,
        { method: 'POST', body: formData }
      );

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Server error ${response.status}`);
      }

      const result = await response.json();

      // Populate chief complaint / reason for visit
      if (result.reason_for_visit) {
        setReason(result.reason_for_visit);
      }

      // Populate diagnoses
      if (result.diagnoses && result.diagnoses.length > 0) {
        setDiagnoses(result.diagnoses.map(d => ({
          code: d.code || '',
          display: d.display || '',
          code_system: d.code_system || 'ICD-10',
          status: d.status || 'provisional',
        })));
      }

      // Build SOAP clinical notes
      if (result.soap) {
        const parts = [];
        if (result.soap.subjective) parts.push(`S: ${result.soap.subjective}`);
        if (result.soap.objective)  parts.push(`O: ${result.soap.objective}`);
        if (result.soap.assessment) parts.push(`A: ${result.soap.assessment}`);
        if (result.soap.plan)       parts.push(`P: ${result.soap.plan}`);
        if (parts.length > 0) setNotes(parts.join('\n\n'));
      }

      // Pre-populate recommended orders (lab + imaging)
      if (result.recommended_orders && result.recommended_orders.length > 0) {
        const newOrders = result.recommended_orders
          .filter(o => o.category === 'lab' || o.category === 'imaging')
          .map(o => ({
            category: o.category,
            test_display: o.test_display || '',
            test_code: o.test_code || '',
            test_code_system: o.test_code_system || (o.category === 'lab' ? 'LOINC' : 'CPT'),
            status: 'requested',
          }));
        if (newOrders.length > 0) {
          setOrders(prev => {
            const existing = new Set(prev.map(o => o.test_display));
            return [...prev, ...newOrders.filter(o => !existing.has(o.test_display))];
          });
          setOrdersExpanded(true);
        }
      }

      // Store chain-of-thought log and show the AI Reasoning panel
      if (result.cot_log && result.cot_log.length > 0) {
        setCotLog(result.cot_log);
        setCotExpanded(false);
      }

    } catch (err) {
      setAiError(`AI processing failed: ${err.message}. You can still fill in the fields manually.`);
    } finally {
      setIsProcessing(false);
    }
  };

  // ── Drug safety check ───────────────────────────────────────────────────────
  const handleSafetyCheck = async () => {
    setSafetyState('loading');
    setSafetyResult(null);
    try {
      const response = await fetch('/drug-check/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          drug_names: prescriptions.map(p => p.medicine_name),
          patient_symptoms: [],
          enable_pubmed_rag: false,
          enable_side_effects: false,
        }),
      });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json();
      setSafetyResult(result);
      setSafetyState('done');
    } catch (err) {
      setSafetyResult({ error: err.message });
      setSafetyState('error');
    }
  };

  // ── Submit ──────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!reason.trim()) return;

    setIsSaving(true);
    setSaveError(null);

    // Build vitals payload only if any value is provided
    let vitalsPayload = null;
    const hasWeight = vitalWeight.trim();
    const hasBp     = vitalSystolic.trim() && vitalDiastolic.trim();
    const hasHr     = vitalHr.trim();
    const hasSpo2   = vitalSpo2.trim();
    if (hasWeight || hasBp || hasHr || hasSpo2) {
      const today = new Date().toISOString().split('T')[0];
      vitalsPayload = {
        weight_kg:       hasWeight ? parseFloat(vitalWeight)       : null,
        systolic_mmhg:   hasBp     ? parseInt(vitalSystolic, 10)   : null,
        diastolic_mmhg:  hasBp     ? parseInt(vitalDiastolic, 10)  : null,
        heart_rate_bpm:  hasHr     ? parseInt(vitalHr, 10)         : null,
        spo2_pct:        hasSpo2   ? parseFloat(vitalSpo2)         : null,
        measured_at:     `${today}T${vitalTime}:00Z`,
      };
    }

    try {
      const response = await fetch(`/ehr/patients/${patient.patient_id}/visits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_reported_reason: reason,
          clinician_notes: notes,
          visit_type: visitType,
          diagnoses: diagnoses.map(d => ({
            code: d.code,
            display: d.display,
            code_system: d.code_system || 'ICD-10',
            status: d.status || 'provisional',
          })),
          prescriptions: prescriptions.map(p => ({
            medicine_name: p.medicine_name,
            inn: p.inn || p.medicine_name,
            dose: p.dose,
            frequency: p.frequency,
            route: p.route || 'oral',
            therapy_type: p.therapy_type || 'acute',
          })),
          vitals: vitalsPayload,
          orders: orders.map(o => ({
            category: o.category,
            test_display: o.test_display,
            test_code: o.test_code || '',
            test_code_system: o.test_code_system || (o.category === 'lab' ? 'LOINC' : 'CPT'),
            status: 'requested',
          })),
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Server error ${response.status}`);
      }

      const { visit_id } = await response.json();

      // Build local visit shape for optimistic display while the page is still open
      onSave({
        visit_id,
        visit_date: new Date().toISOString().split('T')[0],
        patient_reported_reason: reason,
        clinician_notes: notes,
        diagnoses: diagnoses.map(d => ({ display: d.display, code: d.code })),
        prescriptions: prescriptions.map(p => ({ medicine_name: p.medicine_name, dose: p.dose, frequency: p.frequency })),
      });

    } catch (err) {
      setSaveError(`Save failed: ${err.message}`);
      setIsSaving(false);
    }
  };

  // Save enabled when: reason is filled AND (no prescriptions OR safety check was run)
  const canSave = reason.trim().length > 0 &&
    (prescriptions.length === 0 || safetyState === 'done' || safetyState === 'error');

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-4xl mx-auto bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden">
      <div className="bg-slate-900 px-6 py-4 flex justify-between items-center text-white">
        <h2 className="text-lg font-bold">New Visit: {patientName}</h2>
        <span className="text-sm text-slate-400">{new Date().toLocaleDateString()}</span>
      </div>

      <form onSubmit={handleSubmit} className="p-8 space-y-8">

        {/* ── AI Dictation panel ─────────────────────────────────────────────── */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-blue-800 flex items-center">
              <Mic className="w-4 h-4 mr-2" /> AI-Assisted Dictation
            </h3>
            <button
              type="button"
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isProcessing}
              className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isRecording
                  ? 'bg-red-500 text-white hover:bg-red-600 animate-pulse'
                  : isProcessing
                  ? 'bg-blue-300 text-blue-700 cursor-wait'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {isRecording   ? <><MicOff className="w-4 h-4 mr-2" />Stop &amp; Process</>
               : isProcessing ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Processing…</>
               :                <><Mic    className="w-4 h-4 mr-2" />Start Dictation</>}
            </button>
          </div>
          <p className="text-xs text-blue-600">
            Dictate the consultation. MedASR transcribes; the multi-agent pipeline (GP + specialists)
            extracts the chief complaint, ICD-10 diagnoses, SOAP notes, and recommended orders.
            All fields remain editable. Chain-of-thought reasoning is shown in the AI Reasoning panel.
          </p>
          {aiError && (
            <div className="mt-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
              {aiError}
            </div>
          )}
        </div>

        {/* ── AI Reasoning panel (shown after multi-agent pipeline runs) ──────── */}
        {cotLog.length > 0 && (
          <div className="border border-indigo-200 rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setCotExpanded(x => !x)}
              className="w-full flex items-center justify-between px-4 py-3 bg-indigo-50 hover:bg-indigo-100 transition-colors text-left"
            >
              <span className="text-sm font-semibold text-indigo-800">
                AI Reasoning ({cotLog.length} agent{cotLog.length !== 1 ? 's' : ''})
              </span>
              <ChevronDown
                className={`w-4 h-4 text-indigo-500 transition-transform duration-200 ${cotExpanded ? 'rotate-180' : ''}`}
              />
            </button>
            {cotExpanded && (
              <div className="divide-y divide-indigo-100">
                {cotLog.map((entry, idx) => (
                  <CotBlock key={idx} agent={entry.agent} reasoning={entry.reasoning} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Visit type ────────────────────────────────────────────────────── */}
        <div className="flex items-center gap-4">
          <label className="text-sm font-semibold text-slate-700 whitespace-nowrap">Visit Type</label>
          <select
            value={visitType}
            onChange={(e) => setVisitType(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
          >
            {VISIT_TYPES.map(vt => (
              <option key={vt.value} value={vt.value}>{vt.label}</option>
            ))}
          </select>
        </div>

        {/* ── Chief complaint ────────────────────────────────────────────────── */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-2">
            Reason for Visit / Chief Complaint <span className="text-red-500">*</span>
          </label>
          <input
            required
            type="text"
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="e.g. Annual physical, severe headache, etc."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>

        {/* ── Diagnoses (ICD-10 tags) ────────────────────────────────────────── */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-2">Diagnoses (ICD-10)</label>
          <div className="flex flex-wrap gap-2 min-h-[2.25rem] mb-3">
            {diagnoses.length === 0 && (
              <span className="text-xs text-slate-400 italic self-center">
                No diagnoses yet — use dictation or add manually below
              </span>
            )}
            {diagnoses.map((d, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded-full">
                {d.code && <span className="font-bold">[{d.code}]</span>}
                {d.display}
                <button type="button" onClick={() => removeDiagnosis(i)} className="ml-1 text-blue-400 hover:text-red-500">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="ICD code (e.g. J06.9)"
              className="w-36 px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
              value={diagCode}
              onChange={(e) => setDiagCode(e.target.value)}
            />
            <input
              type="text"
              placeholder="Diagnosis description"
              className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
              value={diagDisplay}
              onChange={(e) => setDiagDisplay(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddDiagnosis(); } }}
            />
            <button
              type="button"
              onClick={handleAddDiagnosis}
              disabled={!diagDisplay.trim()}
              className="bg-slate-700 text-white px-4 py-2 rounded-md text-sm hover:bg-slate-600 disabled:opacity-50 transition-colors"
            >
              Add
            </button>
          </div>
        </div>

        {/* ── Clinical notes ─────────────────────────────────────────────────── */}
        <div className="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
          <div className="bg-slate-50 border-b border-slate-200 px-4 py-3">
            <label className="text-sm font-semibold text-slate-700 flex items-center">
              <FileText className="w-4 h-4 mr-2 text-slate-500" />
              {visitType === 'lab_visit'
                ? 'Result Review Notes'
                : 'Clinical Notes (SOAP)'}
              {visitType === 'lab_visit' && (
                <span className="ml-2 text-xs font-normal text-slate-400">optional</span>
              )}
            </label>
            {visitType === 'lab_visit' && (
              <p className="mt-1 text-xs text-slate-400">
                Lab visit — document your interpretation of results and any follow-up plan.
              </p>
            )}
          </div>
          <textarea
            className="w-full p-4 h-40 focus:outline-none focus:ring-inset focus:ring-2 focus:ring-blue-500 resize-none text-slate-800 leading-relaxed text-sm"
            placeholder={
              visitType === 'lab_visit'
                ? 'Interpret results, note any abnormals, and document follow-up plan…'
                : 'S: (Subjective)\n\nO: (Objective)\n\nA: (Assessment)\n\nP: (Plan)'
            }
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>

        {/* ── Vitals (optional) ──────────────────────────────────────────────── */}
        <div className="bg-slate-50 p-5 rounded-xl border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center">
            <Activity className="w-4 h-4 mr-2 text-green-500" /> Vitals
            <span className="ml-2 text-xs font-normal text-slate-400">optional</span>
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Weight (kg)</label>
              <input
                type="number" step="0.1" min="1"
                placeholder="e.g. 72.5"
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                value={vitalWeight}
                onChange={(e) => setVitalWeight(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Systolic (mmHg)</label>
              <input
                type="number" min="50" max="300"
                placeholder="e.g. 120"
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                value={vitalSystolic}
                onChange={(e) => setVitalSystolic(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Diastolic (mmHg)</label>
              <input
                type="number" min="30" max="200"
                placeholder="e.g. 80"
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                value={vitalDiastolic}
                onChange={(e) => setVitalDiastolic(e.target.value)}
              />
            </div>
            <div>
              <label className="flex items-center gap-1 text-xs text-slate-500 mb-1">
                <Heart className="w-3 h-3 text-pink-400" /> Heart Rate (bpm)
              </label>
              <input
                type="number" min="20" max="300"
                placeholder="e.g. 72"
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                value={vitalHr}
                onChange={(e) => setVitalHr(e.target.value)}
              />
            </div>
            <div>
              <label className="flex items-center gap-1 text-xs text-slate-500 mb-1">
                <Wind className="w-3 h-3 text-cyan-400" /> SpO₂ (%)
              </label>
              <input
                type="number" min="50" max="100" step="0.1"
                placeholder="e.g. 98"
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                value={vitalSpo2}
                onChange={(e) => setVitalSpo2(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Time of Measurement</label>
              <input
                type="time"
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                value={vitalTime}
                onChange={(e) => setVitalTime(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* ── Lab & Imaging Orders ───────────────────────────────────────────── */}
        <div className="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden">
          <button
            type="button"
            onClick={() => setOrdersExpanded(x => !x)}
            className="w-full px-6 py-4 flex items-center gap-2 text-left hover:bg-slate-100 transition-colors"
          >
            <ClipboardList className="w-4 h-4 text-indigo-500 flex-shrink-0" />
            <h3 className="text-sm font-semibold text-slate-700">Lab &amp; Imaging Orders</h3>
            <span className="text-xs font-normal text-slate-400">optional</span>
            {orders.length > 0 && (
              <span className="ml-1 inline-flex items-center justify-center w-5 h-5 rounded-full bg-indigo-500 text-white text-xs font-bold">
                {orders.length}
              </span>
            )}
            <ChevronDown
              className={`w-4 h-4 text-slate-400 ml-auto transition-transform duration-200 ${ordersExpanded ? 'rotate-180' : ''}`}
            />
          </button>

          {ordersExpanded && <>
          {/* ── Lab tests ─────────────────────────────────────────────────────── */}
          <div className="px-6 pt-5 pb-4 border-b border-slate-200">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <FlaskConical className="w-3.5 h-3.5 text-indigo-400" /> Lab Tests
            </p>
            {LAB_PANEL_GROUPS.map(group => (
              <div key={group.label} className="mb-3 last:mb-0">
                <p className="text-xs text-slate-400 font-medium mb-1.5">{group.label}</p>
                <div className="flex flex-wrap gap-1.5">
                  {group.tests.map(test => {
                    const already = orders.some(o => o.test_display === test.display);
                    return (
                      <button
                        key={test.code}
                        type="button"
                        onClick={() => handleAddLabPreset(test)}
                        disabled={already}
                        title={`LOINC ${test.code}`}
                        className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                          already
                            ? 'bg-indigo-100 text-indigo-600 border-indigo-200 cursor-default'
                            : 'bg-white text-slate-600 border-slate-300 hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-700'
                        }`}
                      >
                        {already ? '' : '+ '}{test.display}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
            {/* Custom lab entry */}
            <div className="flex gap-2 mt-3">
              <input
                type="text"
                placeholder="Other lab test name"
                className="flex-1 px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                value={customLabName}
                onChange={(e) => setCustomLabName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddCustomLab(); } }}
              />
              <button
                type="button"
                onClick={handleAddCustomLab}
                disabled={!customLabName.trim()}
                className="px-3 py-1.5 bg-slate-700 text-white rounded-md text-sm hover:bg-slate-600 disabled:opacity-40 transition-colors"
              >
                Add
              </button>
            </div>
          </div>

          {/* ── Imaging / studies ─────────────────────────────────────────────── */}
          <div className="px-6 pt-5 pb-4 border-b border-slate-200">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <ImageIcon className="w-3.5 h-3.5 text-blue-400" /> Imaging &amp; Studies
            </p>
            <div className="flex gap-2 items-end flex-wrap">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Modality</label>
                <select
                  value={imgModality}
                  onChange={(e) => { setImgModality(e.target.value); setImgBodyPart(''); }}
                  className="px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  {IMAGING_MODALITIES.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
              {!NO_BODY_PART_MODALITIES.has(imgModality) && (
                <div className="flex-1 min-w-[160px]">
                  <label className="block text-xs text-slate-400 mb-1">Body Part / Region</label>
                  <input
                    list="body-parts-list"
                    type="text"
                    placeholder="e.g. Chest, Knee…"
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500"
                    value={imgBodyPart}
                    onChange={(e) => setImgBodyPart(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddImagingOrder(); } }}
                  />
                  <datalist id="body-parts-list">
                    {COMMON_BODY_PARTS.map(p => <option key={p} value={p} />)}
                  </datalist>
                  {(() => {
                    const key = `${imgModality}_${imgBodyPart.trim()}`;
                    const cpt = IMAGING_CPT_LOOKUP[key];
                    return cpt
                      ? <p className="mt-1 text-xs text-slate-400 font-mono">CPT {cpt}</p>
                      : null;
                  })()}
                </div>
              )}
              <button
                type="button"
                onClick={handleAddImagingOrder}
                disabled={!NO_BODY_PART_MODALITIES.has(imgModality) && !imgBodyPart.trim()}
                className="px-4 py-2 bg-slate-700 text-white rounded-md text-sm hover:bg-slate-600 disabled:opacity-40 transition-colors"
              >
                Add
              </button>
            </div>
          </div>

          {/* ── Order list ────────────────────────────────────────────────────── */}
          {orders.length > 0 ? (
            <ul className="px-6 py-4 space-y-2">
              {orders.map((o, i) => (
                <li key={i} className="flex items-center justify-between bg-white border border-slate-200 px-4 py-2.5 rounded-lg text-sm">
                  <div className="flex items-center gap-2">
                    {o.category === 'imaging'
                      ? <ImageIcon   className="w-4 h-4 text-blue-400 flex-shrink-0" />
                      : <FlaskConical className="w-4 h-4 text-indigo-400 flex-shrink-0" />}
                    <span className="font-medium text-slate-800">{o.test_display}</span>
                    {o.test_code && (
                      <span className="text-xs text-slate-400 font-mono">
                        {o.test_code_system} {o.test_code}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded font-medium uppercase tracking-wide">
                      requested
                    </span>
                    <button type="button" onClick={() => removeOrder(i)} className="text-red-400 hover:text-red-600">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-6 py-4 text-xs text-slate-400 italic">No orders added yet.</p>
          )}
          </>}
        </div>

        {/* ── Prescriptions + safety check ───────────────────────────────────── */}
        <div className="bg-slate-50 p-6 rounded-xl border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center">
            <Pill className="w-4 h-4 mr-2 text-blue-500" /> Prescribe Medication
          </h3>

          <div className="flex gap-3 mb-4">
            <input
              type="text" placeholder="Medication Name"
              className="flex-1 px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 text-sm"
              value={medName} onChange={(e) => setMedName(e.target.value)}
            />
            <input
              type="text" placeholder="Dosage (e.g. 500mg)"
              className="w-1/4 px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 text-sm"
              value={medDosage} onChange={(e) => setMedDosage(e.target.value)}
            />
            <input
              type="text" placeholder="Frequency"
              className="w-1/3 px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 text-sm"
              value={medFreq} onChange={(e) => setMedFreq(e.target.value)}
            />
            <button
              type="button" onClick={handleAddPrescription}
              disabled={!medName || !medDosage}
              className="bg-slate-800 text-white px-4 py-2 rounded-md hover:bg-slate-700 disabled:opacity-50 transition-colors text-sm"
            >
              Add
            </button>
          </div>

          {prescriptions.length > 0 && (
            <>
              <ul className="space-y-2 mb-5">
                {prescriptions.map((p, idx) => (
                  <li key={idx} className="flex justify-between items-center bg-white px-4 py-2 rounded-md border border-slate-200 text-sm">
                    <span>
                      <strong className="text-slate-900">{p.medicine_name}</strong>
                      {p.dose && <span className="text-slate-600"> — {p.dose}</span>}
                      {p.frequency && <span className="text-slate-500"> ({p.frequency})</span>}
                    </span>
                    <button type="button" onClick={() => removePrescription(idx)} className="text-red-400 hover:text-red-600 p-1">
                      <X className="w-4 h-4" />
                    </button>
                  </li>
                ))}
              </ul>

              {/* Drug safety check panel */}
              <div className={`p-4 rounded-lg border ${
                safetyState === 'idle'    ? 'border-amber-300  bg-amber-50'
                : safetyState === 'loading' ? 'border-blue-300   bg-blue-50'
                : safetyState === 'error'   ? 'border-orange-300 bg-orange-50'
                : safetyResult?.critical_count > 0 ? 'border-red-300 bg-red-50'
                : safetyResult?.major_count    > 0 ? 'border-orange-300 bg-orange-50'
                : 'border-green-300 bg-green-50'
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {safetyState === 'loading'
                      ? <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                      : <Shield className={`w-5 h-5 ${
                          safetyState === 'idle'    ? 'text-amber-500'
                          : safetyState === 'error' ? 'text-orange-500'
                          : safetyResult?.critical_count > 0 ? 'text-red-600'
                          : safetyResult?.major_count    > 0 ? 'text-orange-500'
                          : 'text-green-600'
                        }`} />
                    }
                    <span className={`text-sm font-semibold ${
                      safetyState === 'idle'    ? 'text-amber-700'
                      : safetyState === 'loading' ? 'text-blue-700'
                      : safetyState === 'error'   ? 'text-orange-700'
                      : safetyResult?.critical_count > 0 ? 'text-red-700'
                      : safetyResult?.major_count    > 0 ? 'text-orange-700'
                      : 'text-green-700'
                    }`}>
                      {safetyState === 'idle'    && 'Safety check required before saving'}
                      {safetyState === 'loading' && 'Checking drug interactions…'}
                      {safetyState === 'error'   && 'Safety check error — review and confirm before saving'}
                      {safetyState === 'done' && (
                        safetyResult?.critical_count > 0
                          ? `CRITICAL: ${safetyResult.critical_count} critical interaction(s) found`
                          : safetyResult?.major_count > 0
                          ? `WARNING: ${safetyResult.major_count} major interaction(s) found`
                          : 'No significant interactions detected'
                      )}
                    </span>
                  </div>
                  {safetyState === 'idle' && (
                    <button
                      type="button"
                      onClick={handleSafetyCheck}
                      className="flex items-center px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                      <Shield className="w-4 h-4 mr-2" /> Check Medication Safety
                    </button>
                  )}
                  {(safetyState === 'done' || safetyState === 'error') && (
                    <button
                      type="button"
                      onClick={() => { setSafetyState('idle'); setSafetyResult(null); }}
                      className="text-xs text-slate-500 hover:text-slate-700 underline"
                    >
                      Re-check
                    </button>
                  )}
                </div>

                {/* Interaction details */}
                {safetyState === 'done' && safetyResult?.interactions?.length > 0 && (
                  <div className="mt-3 space-y-1.5">
                    {safetyResult.interactions.map((ix, i) => (
                      <div key={i} className={`text-xs p-2 rounded border ${
                        ix.severity === 'critical' ? 'bg-red-50    border-red-200    text-red-800'
                        : ix.severity === 'major'  ? 'bg-orange-50 border-orange-200 text-orange-800'
                        :                            'bg-yellow-50 border-yellow-200 text-yellow-800'
                      }`}>
                        <strong className="uppercase">{ix.severity}</strong>: {ix.drug_a} + {ix.drug_b}
                        <br /><span className="opacity-80">{ix.description}</span>
                      </div>
                    ))}
                  </div>
                )}
                {safetyState === 'done' && safetyResult?.recommendations?.length > 0 && (
                  <ul className="mt-2 space-y-0.5">
                    {safetyResult.recommendations.map((r, i) => (
                      <li key={i} className="text-xs text-slate-600">{r}</li>
                    ))}
                  </ul>
                )}
                {safetyState === 'error' && (
                  <div className="mt-3 text-sm text-orange-900 bg-orange-100 border border-orange-300 rounded px-3 py-2">
                    <strong>Error:</strong>{' '}
                    {safetyResult?.error || 'Safety check failed — check server connection and try again.'}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* ── File attachments ───────────────────────────────────────────────── */}
        <div>
          <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center">
            <Upload className="w-4 h-4 mr-2 text-slate-500" /> Attach Lab Results / Imaging
            <span className="ml-2 text-xs font-normal text-slate-400">optional</span>
          </h3>
          <input type="file" ref={fileInputRef} multiple accept=".pdf,image/*"
            onChange={handleFileChange} className="hidden" />
          <div
            onClick={() => fileInputRef.current.click()}
            className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center hover:bg-slate-50 hover:border-blue-400 cursor-pointer transition-colors"
          >
            <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
            <p className="text-sm text-slate-600 font-medium">Click to upload or drag and drop</p>
            <p className="text-xs text-slate-400 mt-1">PDF, JPG, PNG</p>
          </div>
          {attachments.length > 0 && (
            <div className="mt-4 grid grid-cols-2 gap-3">
              {attachments.map((file, idx) => (
                <div key={idx} className="flex items-center justify-between bg-slate-50 border border-slate-200 p-2 rounded-lg">
                  <div className="flex items-center overflow-hidden">
                    {file.type.includes('pdf')
                      ? <File      className="w-5 h-5 text-red-500  mr-2 flex-shrink-0" />
                      : <ImageIcon className="w-5 h-5 text-blue-500 mr-2 flex-shrink-0" />}
                    <span className="text-sm text-slate-700 truncate">{file.name}</span>
                  </div>
                  <button type="button" onClick={() => removeAttachment(idx)} className="text-slate-400 hover:text-red-500 ml-2">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Save error ─────────────────────────────────────────────────────── */}
        {saveError && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
            {saveError}
          </div>
        )}

        {/* ── Actions ────────────────────────────────────────────────────────── */}
        <div className="flex justify-end space-x-4 pt-6 border-t border-slate-200">
          <button
            type="button" onClick={onCancel} disabled={isSaving}
            className="px-6 py-2.5 border border-slate-300 rounded-lg text-slate-700 font-medium hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSave || isSaving}
            title={
              !reason.trim() ? 'Enter chief complaint first'
              : prescriptions.length > 0 && safetyState === 'idle' ? 'Run medication safety check first'
              : ''
            }
            className={`px-6 py-2.5 rounded-lg font-medium flex items-center transition-colors ${
              canSave && !isSaving
                ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm'
                : 'bg-slate-200 text-slate-400 cursor-not-allowed'
            }`}
          >
            {isSaving
              ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving…</>
              : <><CheckCircle2 className="w-5 h-5 mr-2" />Save Visit Record</>}
          </button>
        </div>

      </form>
    </div>
  );
}
