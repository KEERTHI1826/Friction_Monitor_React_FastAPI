import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, CheckCircle2, ChevronDown, CircleHelp, CloudUpload, Download, Filter, Gauge, Layers3, RefreshCw, Search, ShieldCheck, Sparkles, Workflow } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './styles.css'


const API = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "")

const fmt = (n) => Number(n ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })
const initialForm = { project_id: 'P001', task_id: 'T001', task_name: 'Requirement Collection', planned_days: 4, actual_days: 6, response_delay: 2, rework_count: 1, dependency_count: 2, team_workload: 76 }

function App() {
  const [summary, setSummary] = useState(null)
  const [items, setItems] = useState([])
  const [query, setQuery] = useState('')
  const [level, setLevel] = useState('All levels')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [apiUp, setApiUp] = useState(false)
  const [form, setForm] = useState(initialForm)
  const [scoreResult, setScoreResult] = useState(null)
  const [scoring, setScoring] = useState(false)
  const [notice, setNotice] = useState('')

  async function loadData() {
    setBusy(true); setError('')
    try {
      const [s, t, h] = await Promise.all([
        fetch(`${API}/api/summary`), fetch(`${API}/api/tasks?limit=100`), fetch(`${API}/health`)
      ])
      if (!s.ok || !t.ok || !h.ok) throw new Error('API request failed. Check that the FastAPI backend is running.')
      setSummary(await s.json())

      setItems((await t.json()).tasks || [])

    } catch (e) { setError(e.message || 'Cannot reach the backend.'); setApiUp(false) }
    finally { setBusy(false) }
  }
  useEffect(() => { loadData() }, [])

  const filtered = useMemo(() => items.filter((r) => {
    const matchLevel = level === 'All levels' || r.friction_level === level
    const q = query.trim().toLowerCase()
    const matchText = !q || `${r.project_id} ${r.task_name} ${r.task_id}`.toLowerCase().includes(q)
    return matchLevel && matchText
  }), [items, level, query])

  const chartData = useMemo(() => {
    const names = ['Requirement', 'API integration', 'Migration', 'Configuration', 'Testing', 'Approval', 'Deployment']
    return names.map((name, idx) => {
      const group = items.filter((r) => r.task_name === ['Requirement Collection', 'API Integration', 'Data Migration', 'Configuration', 'Testing', 'Customer Approval', 'Deployment'][idx])
      return { name, friction: group.length ? +(group.reduce((a, b) => a + b.friction_score, 0) / group.length).toFixed(1) : 0 }
    })
  }, [items])

  async function runScore(e) {
    e.preventDefault(); setScoring(true); setScoreResult(null)
    try {
      const res = await fetch(`${API}/api/score`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...form, planned_days: Number(form.planned_days), actual_days: Number(form.actual_days), response_delay: Number(form.response_delay), rework_count: Number(form.rework_count), dependency_count: Number(form.dependency_count), team_workload: Number(form.team_workload) }) })
      const body = await res.json()
      if (!res.ok) throw new Error(body.detail || 'Could not calculate score')
      setScoreResult(body)
    } catch (e) { setError(e.message) }
    finally { setScoring(false) }
  }
  async function uploadCsv(e) {
    const file = e.target.files?.[0]; if (!file) return
    const fd = new FormData(); fd.append('file', file); setNotice('')
    try {
      const res = await fetch(`${API}/api/upload-csv`, { method: 'POST', body: fd }); const body = await res.json()
      if (!res.ok) throw new Error(body.detail || 'Upload failed')
      setNotice(`${body.rows} rows imported successfully.`); await loadData()
    } catch (err) { setError(err.message) }
    e.target.value = ''
  }
  async function resetSample() {
    try { const res = await fetch(`${API}/api/reset-sample`, { method: 'POST' }); if (!res.ok) throw new Error('Could not reset sample data'); setNotice('Sample dataset restored.'); await loadData() }
    catch (e) { setError(e.message) }
  }
  function exportCsv() {
    const cols = ['project_id', 'task_id', 'task_name', 'planned_days', 'actual_days', 'friction_score', 'friction_level', 'bottleneck_score', 'recommended_action']
    const csv = [cols.join(','), ...filtered.map(row => cols.map(c => `"${String(row[c] ?? '').replaceAll('"', '""')}"`).join(','))].join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }))
    const a = document.createElement('a'); a.href = url; a.download = 'workflow-bottleneck-results.csv'; a.click(); URL.revokeObjectURL(url)
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Workflow size={22} /></div><div><strong>FlowPilot</strong><span>WORKFLOW INTELLIGENCE</span></div></div>
      <div className="side-label">WORKSPACE</div>
      <div className="nav-item active"><Layers3 size={17} /> Overview <span className="nav-dot" /></div>
      <div className="nav-item"><Activity size={17} /> Friction analysis</div>
      <div className="nav-item"><AlertTriangle size={17} /> Bottlenecks</div>
      <div className="nav-item"><Gauge size={17} /> Score a task</div>
      <div className="sidebar-bottom">
        <div className="side-card"><div className="side-card-icon"><ShieldCheck size={18} /></div><b>Operational clarity</b><p>Turn workflow signals into clear next steps.</p></div>
        <div className="profile"><div className="avatar">WF</div><div><b>Workflow Monitor</b><span>Project workspace</span></div><ChevronDown size={15} /></div>
      </div>
    </aside>

    <main className="main">
      <header className="topbar"><div className="breadcrumbs">Workspace <span>/</span> <b>Overview</b></div><div className="top-actions"><span className={`api-status ${apiUp ? 'online' : 'offline'}`}><i /> {apiUp ? 'API connected' : 'API disconnected'}</span><button className="icon-button" onClick={loadData} title="Refresh data"><RefreshCw size={16} /></button><div className="mini-avatar">L</div></div></header>
      <div className="content">
        <div className="welcome-row"><div><div className="eyebrow"><Sparkles size={13} /> WORKFLOW INTELLIGENCE</div><h1>Workflow overview</h1><p className="subtitle">Spot friction early. Unblock work with confidence.</p></div><div className="header-buttons"><label className="button secondary upload-button"><CloudUpload size={16} /> Import CSV<input type="file" accept=".csv,text/csv" onChange={uploadCsv} /></label><button className="button primary" onClick={exportCsv}><Download size={16} /> Export report</button></div></div>
        {error && <div className="alert error"><AlertTriangle size={17} /><span>{error}</span><button onClick={() => setError('')}>Dismiss</button></div>}
        {notice && <div className="alert success"><CheckCircle2 size={17} />{notice}<button onClick={() => setNotice('')}>Dismiss</button></div>}
        {!apiUp && <div className="alert warning"><CircleHelp size={17} /><span>Start the FastAPI server, then refresh. The UI is ready but live data needs the backend.</span></div>}

        <section className="metric-grid">
          <Metric title="Tasks monitored" value={summary ? fmt(summary.total_tasks) : '—'} hint="Across the active dataset" icon={<Layers3 size={19} />} tone="blue" />
          <Metric title="High-friction tasks" value={summary ? fmt(summary.high_risk) : '—'} hint={summary ? `${summary.total_tasks ? Math.round(summary.high_risk / summary.total_tasks * 100) : 0}% of monitored tasks` : 'Awaiting backend'} icon={<AlertTriangle size={19} />} tone="orange" trend="risk" />
          <Metric title="Average friction" value={summary ? `${fmt(summary.average_friction)}%` : '—'} hint="Weighted operational score" icon={<Activity size={19} />} tone="purple" />
          <Metric title="Avg. bottleneck score" value={summary ? fmt(summary.average_bottleneck) : '—'} hint="Friction + dependencies" icon={<Gauge size={19} />} tone="green" />
        </section>

        <section className="middle-grid">
          <div className="panel chart-panel"><div className="panel-head"><div><h2>Friction by workflow stage</h2><p>Average friction score for each task type</p></div><span className="period-pill">All projects <ChevronDown size={13} /></span></div>
            <div className="chart-legend"><span className="legend-dot" /> Average friction <span className="legend-note">· Score out of 100</span></div>
            <div className="chart-wrap">{chartData.some(d => d.friction > 0) ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData} margin={{ top: 10, right: 12, left: -18, bottom: 0 }}><defs><linearGradient id="frictionFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6c70f5" stopOpacity={0.25} /><stop offset="95%" stopColor="#6c70f5" stopOpacity={0.01} /></linearGradient></defs><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#edf0f6" /><XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#858ca0', fontSize: 10 }} interval={0} /><YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: '#858ca0', fontSize: 10 }} /><Tooltip formatter={(v) => [`${v}%`, 'Friction']} contentStyle={{ border: '1px solid #e8ebf2', borderRadius: 12, fontSize: 12 }} /><Area type="monotone" dataKey="friction" stroke="#6c70f5" strokeWidth={2.5} fill="url(#frictionFill)" activeDot={{ r: 5 }} /></AreaChart></ResponsiveContainer> : <div className="empty-chart">Connect to the API to load workflow trends.</div>}</div>
          </div>
          <div className="panel insight-panel"><div className="panel-head"><div><h2>Risk distribution</h2><p>Tasks grouped by friction level</p></div><span className="tiny-more">•••</span></div>
            <div className="risk-total"><strong>{summary ? fmt(summary.total_tasks) : '—'}</strong><span>total tasks</span></div>
            <div className="risk-bar"><span className="risk-low" style={{ width: `${summary?.total_tasks ? (summary.levels?.Low || 0) / summary.total_tasks * 100 : 0}%` }} /><span className="risk-mid" style={{ width: `${summary?.total_tasks ? (summary.levels?.Moderate || 0) / summary.total_tasks * 100 : 0}%` }} /><span className="risk-high" style={{ width: `${summary?.total_tasks ? (summary.levels?.High || 0) / summary.total_tasks * 100 : 0}%` }} /></div>
            <RiskRow color="low" label="Low friction" count={summary?.levels?.Low ?? 0} total={summary?.total_tasks ?? 0} />
            <RiskRow color="mid" label="Moderate friction" count={summary?.levels?.Moderate ?? 0} total={summary?.total_tasks ?? 0} />
            <RiskRow color="high" label="High friction" count={summary?.levels?.High ?? 0} total={summary?.total_tasks ?? 0} />
            <button className="text-link" onClick={() => { setLevel('High'); document.getElementById('bottlenecks')?.scrollIntoView({ behavior: 'smooth' }) }}>Review high-friction tasks <ArrowUpRight size={15} /></button>
          </div>
        </section>

        <section className="panel table-panel" id="bottlenecks"><div className="panel-head table-heading"><div><h2>Priority bottlenecks</h2><p>Ranked by bottleneck score · Highest impact first</p></div><button className="button secondary small" onClick={exportCsv}><Download size={15} /> Export CSV</button></div>
          <div className="table-tools"><div className="search-box"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search project or task..." /></div><div className="filter-box"><Filter size={15} /><select value={level} onChange={e => setLevel(e.target.value)}><option>All levels</option><option>Low</option><option>Moderate</option><option>High</option></select></div><button className="button ghost small" onClick={() => { setQuery(''); setLevel('All levels') }}>Reset</button></div>
          <div className="table-scroll"><table><thead><tr><th>PROJECT / TASK</th><th>FRICTION SCORE</th><th>BOTTLENECK SCORE</th><th>LEVEL</th><th>RECOMMENDED NEXT STEP</th></tr></thead><tbody>
            {filtered.slice(0, 12).map((r, i) => <tr key={`${r.project_id}-${r.task_id}`}><td><div className="task-cell"><div className={`task-icon task-${r.friction_level?.toLowerCase()}`}>{r.task_name?.slice(0, 1)}</div><div><b>{r.task_name}</b><span>{r.project_id} · {r.task_id}</span></div></div></td><td><div className="score-cell"><b>{fmt(r.friction_score)}</b><div className="mini-track"><i style={{ width: `${Math.min(100, r.friction_score)}%` }} /></div></div></td><td><b>{fmt(r.bottleneck_score)}</b></td><td><span className={`level-pill ${r.friction_level?.toLowerCase()}`}>{r.friction_level}</span></td><td className="action-text">{r.recommended_action}</td></tr>)}
            {!filtered.length && <tr><td colSpan="5" className="empty-table">{busy ? 'Loading tasks...' : 'No tasks match these filters.'}</td></tr>}
          </tbody></table></div><div className="table-foot"><span>Showing <b>{Math.min(filtered.length, 12)}</b> of <b>{filtered.length}</b> matching tasks</span><button className="text-link" onClick={() => loadData()}>Refresh results <RefreshCw size={13} /></button></div>
        </section>

        <section className="bottom-grid">
          <div className="panel scorer-panel"><div className="panel-head"><div><h2>Score a task</h2><p>Estimate friction from current task signals</p></div><span className="pill-icon"><Gauge size={17} /></span></div>
            <form onSubmit={runScore}><div className="form-grid">
              <Field label="Project ID"><input value={form.project_id} onChange={e => setForm({ ...form, project_id: e.target.value })} /></Field>
              <Field label="Task name"><select value={form.task_name} onChange={e => setForm({ ...form, task_name: e.target.value })}>{['Requirement Collection', 'API Integration', 'Data Migration', 'Configuration', 'Testing', 'Customer Approval', 'Deployment'].map(x => <option key={x}>{x}</option>)}</select></Field>
              <Field label="Planned days"><input type="number" min="1" max="3650" required value={form.planned_days} onChange={e => setForm({ ...form, planned_days: e.target.value })} /></Field>
              <Field label="Actual days"><input type="number" min="1" max="3650" required value={form.actual_days} onChange={e => setForm({ ...form, actual_days: e.target.value })} /></Field>
              <Field label="Response delay (days)"><input type="number" min="0" max="100" value={form.response_delay} onChange={e => setForm({ ...form, response_delay: e.target.value })} /></Field>
              <Field label="Rework count"><input type="number" min="0" max="100" value={form.rework_count} onChange={e => setForm({ ...form, rework_count: e.target.value })} /></Field>
              <Field label="Dependencies"><input type="number" min="0" max="100" value={form.dependency_count} onChange={e => setForm({ ...form, dependency_count: e.target.value })} /></Field>
              <Field label="Team workload (%)"><input type="number" min="0" max="100" value={form.team_workload} onChange={e => setForm({ ...form, team_workload: e.target.value })} /></Field>
            </div><button className="button primary score-button" disabled={scoring}>{scoring ? 'Calculating…' : <><Sparkles size={15} /> Calculate friction score</>}</button></form>
            {scoreResult && <div className="score-result"><div><span>FRICTION SCORE</span><strong>{fmt(scoreResult.friction_score)}<small>/100</small></strong><em className={`level-pill ${scoreResult.friction_level.toLowerCase()}`}>{scoreResult.friction_level}</em></div><div><span>BOTTLENECK SCORE</span><strong>{fmt(scoreResult.bottleneck_score)}<small>/100*</small></strong></div><p>{scoreResult.recommended_action}</p></div>}
          </div>
          <div className="panel method-panel"><div className="panel-head"><div><h2>How scoring works</h2><p>Transparent, weighted indicators</p></div><span className="pill-icon"><CircleHelp size={17} /></span></div>
            <div className="formula-row"><span className="formula-num">01</span><div><b>Delay score <span>30%</span></b><p>Actual duration compared with planned duration.</p></div></div>
            <div className="formula-row"><span className="formula-num">02</span><div><b>Response delay <span>20%</span></b><p>Slow customer or stakeholder responses.</p></div></div>
            <div className="formula-row"><span className="formula-num">03</span><div><b>Rework + dependencies <span>30%</span></b><p>Repeated work and blocked task connections.</p></div></div>
            <div className="formula-row"><span className="formula-num">04</span><div><b>Team workload <span>20%</span></b><p>Current workload percentage contributes to friction.</p></div></div>
            <div className="method-note"><CircleHelp size={15} /><span>*Bottleneck score is a rule-based ranking indicator. The bundled demo dataset is synthetic, not real customer data.</span></div>
          </div>
        </section>
        <footer><span>FlowPilot · Workflow Friction Monitor</span><span>Built for clearer decisions <span className="footer-dot">•</span> <a href={`${API}/docs`} target="_blank" rel="noreferrer">API documentation <ArrowDownRight size={12} /></a></span></footer>
      </div>
    </main>
  </div>
}
function Metric({ title, value, hint, icon, tone, trend }) { return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-title">{title}</div><div className="metric-value">{value}</div><div className="metric-hint">{trend === 'risk' ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />} {hint}</div></div> }
function RiskRow({ color, label, count, total }) { return <div className="risk-row"><span className={`risk-dot ${color}`} /><span className="risk-label">{label}</span><b>{fmt(count)}</b><span className="risk-percent">{total ? Math.round(count / total * 100) : 0}%</span></div> }
function Field({ label, children }) { return <label className="field"><span>{label}</span>{children}</label> }
createRoot(document.getElementById('root')).render(<App />)
