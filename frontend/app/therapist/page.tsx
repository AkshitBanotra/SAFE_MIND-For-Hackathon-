'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Activity, Bell, CalendarDays, ChevronDown, Clock3, Moon, RefreshCw, Sun } from 'lucide-react'
import './therapist.css'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
type Point = { date: string; value: number | null }
type Summary = { date?: string; assessment_report?: string }
type AlertItem = { id: string | number; message: string; text?: string; title?: string; created_at?: string; severity?: string; read?: boolean }
const formatDateLocal = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const normalizeDate = (value: string, fallback: string) => {
  const isoDate = value.match(/^(\d{4}-\d{2}-\d{2})/)
  if (isoDate) return isoDate[1]
  const humanDate = value.match(/^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$/)
  if (humanDate) {
    const month = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'].indexOf(humanDate[2].toLowerCase())
    if (month >= 0) return `${humanDate[3]}-${String(month + 1).padStart(2, '0')}-${humanDate[1].padStart(2, '0')}`
  }
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? fallback : formatDateLocal(parsed)
}

export default function TherapistDashboard() {
  const [dark, setDark] = useState(false)
  const [demo, setDemo] = useState(false)
  const [period, setPeriod] = useState<'week' | 'month'>('week')
  const [points, setPoints] = useState<Point[]>([])
  const [demoPoints, setDemoPoints] = useState<Point[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [alertSounds, setAlertSounds] = useState<string[]>([])
  const [selectedSound, setSelectedSound] = useState('')
  const [alertsOpen, setAlertsOpen] = useState(false)
  const [readOverrides, setReadOverrides] = useState<Record<string, boolean>>({})
  const [readStateLoaded, setReadStateLoaded] = useState(false)
  const alertsRef = useRef<AlertItem[]>([])
  const selectedSoundRef = useRef(selectedSound)
  const alertMenuRef = useRef<HTMLDivElement>(null)
  const pointsRef = useRef<Point[]>([])
  const demoPointsRef = useRef<Point[]>([])
  const summaryFetchedDateRef = useRef<string | null>(null)

  const loadReport = useCallback(async () => {
    setLoading(true)
    try {
      const root = API_URL.replace(/\/$/, '')
      const scoreResponse = await fetch(`${root}/therapist/distress/today`, { headers: { Accept: 'application/json' }, cache: 'no-store' })
      if (!scoreResponse.ok && scoreResponse.status !== 404) throw new Error(`Distress score request returned ${scoreResponse.status}.`)
      let scoreDate = formatDateLocal(new Date())
      let newPoint: Point | null = null
      if (scoreResponse.ok) {
        const responseText = await scoreResponse.text()
        if (responseText.trim()) {
          const parsed: unknown = JSON.parse(responseText)
          if (typeof parsed === 'object' && parsed !== null) {
            const scoreData = parsed as { date?: string; value?: number | null; score?: number | null; distress_index?: number | null; distress_score?: number | null }
            if (scoreData.date) scoreDate = normalizeDate(scoreData.date, scoreDate)
            const rawValue = scoreData.value ?? scoreData.score ?? scoreData.distress_index ?? scoreData.distress_score
            if (rawValue !== undefined && rawValue !== null && Number.isFinite(Number(rawValue))) {
              newPoint = { date: scoreDate, value: Math.max(0, Math.min(100, Number(rawValue))) }
            }
          }
        }
      }
      const historyKey = demo ? 'safemind-therapist-demo-history' : 'safemind-therapist-distress-history'
      let savedPoints: Point[] = []
      try {
        const saved = localStorage.getItem(historyKey)
        if (saved) savedPoints = JSON.parse(saved) as Point[]
      } catch { /* A missing or invalid cache just starts a new local history. */ }
      if (demo) {
        const history = [...savedPoints, ...demoPointsRef.current.filter(p => !savedPoints.some(s => s.date === p.date))]
        const maxDay = history.reduce((max, p) => Math.max(max, Number(p.date.slice(5)) || 0), 0)
        if (newPoint) history.push({ date: `demo-${maxDay + 1}`, value: newPoint.value })
        demoPointsRef.current = history
        setDemoPoints(history)
        try { localStorage.setItem(historyKey, JSON.stringify(history)) }
        catch { /* The current session can still display the scores without storage. */ }
      } else {
        const byDate = new Map<string, Point>()
        for (const point of [...savedPoints, ...pointsRef.current]) byDate.set(point.date.slice(0, 10), point)
        if (newPoint) byDate.set(newPoint.date, newPoint)
        const history = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
        pointsRef.current = history
        setPoints(history)
        try { localStorage.setItem(historyKey, JSON.stringify(history)) }
        catch { /* The current session can still display the scores without storage. */ }
      }

      const summaryRequestDate = formatDateLocal(new Date())
      // Demo mode polls the distress endpoint every five minutes, so poll the
      // summary endpoint on those same refreshes instead of reusing the
      // once-per-day guard from the live dashboard.
      if (demo || summaryFetchedDateRef.current !== summaryRequestDate) {
        summaryFetchedDateRef.current = summaryRequestDate
        try {
          const summaryResponse = await fetch(`${root}/therapist/summary`, { headers: { Accept: 'application/json' }, cache: 'no-store' })
          if (summaryResponse.ok) {
            const summaryText = await summaryResponse.text()
            setSummary(summaryText.trim() ? JSON.parse(summaryText) as Summary : null)
          }
          else if (summaryResponse.status === 404 || summaryResponse.status === 204) setSummary(null)
          else throw new Error(`Daily summary request returned ${summaryResponse.status}.`)
        }
        catch (error) {
          summaryFetchedDateRef.current = null
          throw error
        }
      }
      setLastUpdated(new Date())
    } catch { /* Leave the dashboard in its quiet empty or last-known-data state. */ }
    finally { setLoading(false) }
  }, [demo])

  useEffect(() => {
    try {
      const saved = localStorage.getItem('safemind-therapist-distress-history')
      if (saved) {
        const history = JSON.parse(saved) as Point[]
        pointsRef.current = history
        setPoints(history)
      }
    } catch { /* A missing or invalid cache starts with an empty graph. */ }
    try {
      const saved = localStorage.getItem('safemind-therapist-demo-history')
      if (saved) {
        const history = JSON.parse(saved) as Point[]
        demoPointsRef.current = history
        setDemoPoints(history)
      }
    } catch { /* A missing or invalid demo cache starts at Demo day 1. */ }
    void loadReport()
  }, [loadReport])
  useEffect(() => {
    if (demo) return
    const msUntilMidnight = () => { const n = new Date(); const next = new Date(n); next.setHours(24, 0, 5, 0); return next.getTime() - n.getTime() }
    let timer: ReturnType<typeof setTimeout>
    const schedule = () => { timer = setTimeout(() => { void loadReport(); schedule() }, msUntilMidnight()) }
    schedule()
    return () => clearTimeout(timer)
  }, [demo, loadReport])
  useEffect(() => {
    if (!demo) return
    const timer = setInterval(() => { void loadReport() }, 300_000)
    return () => clearInterval(timer)
  }, [demo, loadReport])
  useEffect(() => {
    let active = true
    const loadExisting = async () => {
      try {
        const r = await fetch(`${API_URL.replace(/\/$/, '')}/therapist/alerts`, { headers: { Accept: 'application/json' }, cache: 'no-store' })
        if (!r.ok) return
        const body: unknown = await r.json()
        const items: AlertItem[] = Array.isArray(body) ? body : (typeof body === 'object' && body !== null && 'alerts' in body && Array.isArray(body.alerts) ? body.alerts : [])
        const next = items.map(item => ({ ...item, message: item.message ?? item.text ?? item.title ?? '' }))
        if (!active) return
        const merged = [...alertsRef.current]
        for (const item of next) if (!merged.some(existing => String(existing.id) === String(item.id))) merged.push(item)
        alertsRef.current = merged
        setAlerts(merged)
      } catch { /* The next poll will retry if the service is unavailable. */ }
    }
    void loadExisting()
    const stream = new EventSource(`${API_URL.replace(/\/$/, '')}/therapist/alerts/stream`)
    const receive = (event: Event) => {
      try {
        const alert = JSON.parse((event as MessageEvent<string>).data) as AlertItem
        if (alert.id == null) return
        const normalized = { ...alert, message: alert.message ?? alert.text ?? alert.title ?? '' }
        const known = alertsRef.current.some(item => String(item.id) === String(normalized.id))
        if (known) return
        alertsRef.current = [normalized, ...alertsRef.current]
        setAlerts(alertsRef.current)
        if (selectedSoundRef.current) {
          const audio = new Audio(`/api/alert-sounds/${encodeURIComponent(selectedSoundRef.current)}`)
          void audio.play().catch(() => {})
        }
      } catch { /* Ignore malformed events and keep the stream open. */ }
    }
    stream.addEventListener('alert', receive)
    stream.onmessage = receive
    return () => { active = false; stream.removeEventListener('alert', receive); stream.onmessage = null; stream.close() }
  }, [])
  useEffect(() => { selectedSoundRef.current = selectedSound }, [selectedSound])
  useEffect(() => {
    try {
      const saved = localStorage.getItem('safemind-therapist-alert-read-state')
      if (saved) setReadOverrides(JSON.parse(saved) as Record<string, boolean>)
    } catch { /* Read-state persistence is optional. */ }
    setReadStateLoaded(true)
  }, [])
  useEffect(() => {
    if (!readStateLoaded) return
    try { localStorage.setItem('safemind-therapist-alert-read-state', JSON.stringify(readOverrides)) }
    catch { /* Read-state persistence is optional. */ }
  }, [readOverrides, readStateLoaded])
  useEffect(() => {
    void fetch('/api/alert-sounds').then(r => r.ok ? r.json() : []).then((files: string[]) => {
      setAlertSounds(files)
      if (files.length) setSelectedSound(files[0])
    }).catch(() => setAlertSounds([]))
  }, [])
  useEffect(() => {
    const close = (event: MouseEvent) => { if (!alertMenuRef.current?.contains(event.target as Node)) setAlertsOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  const isRead = (alert: AlertItem) => readOverrides[String(alert.id)] ?? Boolean(alert.read)
  const unreadCount = alerts.filter(a => !isRead(a)).length
  function setAlertRead(alert: AlertItem, read: boolean) {
    const id = String(alert.id)
    setReadOverrides(current => ({ ...current, [id]: read }))
  }

  const chart = useMemo(() => {
    const count = period === 'week' ? 7 : 30
    const visiblePoints = demo ? demoPoints : points
    const entries = demo
      ? Array.from({ length: count }, (_, i) => {
          const recent = visiblePoints.slice(-count)
          const point = recent[i]
          return { date: new Date(0), label: point ? `Demo day ${Number(point.date.slice(5))}` : '', value: point?.value ?? null }
        })
      : Array.from({ length: count }, (_, i) => {
          const now = new Date()
          const date = new Date(now); date.setDate(now.getDate() - (count - 1 - i))
          const key = formatDateLocal(date)
          const found = visiblePoints.find((p) => p.date.slice(0, 10) === key)
          return { date, label: '', value: found?.value ?? null }
        })
    const W = 760, H = 250, left = 36, right = 18, top = 16, bottom = 30
    const x = (i: number) => left + (i / Math.max(1, count - 1)) * (W - left - right)
    const y = (v: number) => top + ((100 - v) / 100) * (H - top - bottom)
    const line = entries.map((p, i) => p.value === null ? null : `${i === 0 || entries[i - 1].value === null ? 'M' : 'L'} ${x(i)} ${y(p.value)}`).filter(Boolean).join(' ')
    return { entries, W, H, left, right, top, bottom, x, y, line }
  }, [period, points, demo, demoPoints])
  const visiblePoints = demo ? demoPoints : points
  const latest = [...visiblePoints].reverse().find((p) => p.value !== null)?.value
  const periodReadings = chart.entries.filter((p): p is { date: Date; value: number } => p.value !== null)
  const average = periodReadings.reduce((sum, p) => sum + p.value, 0) / (periodReadings.length || 1)
  const hasChartData = periodReadings.length > 0

  return <main className={`therapist-shell ${dark ? 'tdark' : ''}`}>
    <header className="tbar">
      <div className="tbrand"><div className="tlogo"><BrainIcon /></div><div><strong>SafeMind</strong><small>THERAPIST PORTAL</small></div></div>
      <div className="tbar-right"><span className="secure-label"><span /> PRIVATE WORKSPACE</span><div className="alert-menu" ref={alertMenuRef}><button className="ticon notification-bell" aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ''}`} aria-expanded={alertsOpen} onClick={() => setAlertsOpen(v => !v)}><Bell />{unreadCount > 0 && <i className="bell-count">{unreadCount > 99 ? '99+' : unreadCount}</i>}</button>{alertsOpen && <div className="notification-popover"><div className="notification-head"><div><b>Notifications</b><small>{unreadCount ? `${unreadCount} unread` : 'All caught up'}</small></div><button onClick={() => alerts.forEach(a => { if (!isRead(a)) void setAlertRead(a, true) })} disabled={!unreadCount}>Mark all read</button></div><div className="notification-items">{alerts.length ? alerts.map(a => { const read = isRead(a); return <article className={`notification-item ${read ? 'is-read' : ''}`} key={a.id}><span className="notification-dot"/><div><div className="notification-meta"><b>{a.title ?? a.severity ?? 'Client notification'}</b><small>{a.created_at ? new Date(a.created_at).toLocaleString() : ''}</small></div><p>{a.message}</p><button onClick={() => void setAlertRead(a, !read)}>{read ? 'Mark unread' : 'Mark read'}</button></div></article> }) : <div className="notifications-empty"><Bell size={18}/><span>No notifications yet</span></div>}</div><label className="sound-setting">Alert sound<select value={selectedSound} onChange={e => setSelectedSound(e.target.value)} disabled={!alertSounds.length}>{alertSounds.map(sound => <option key={sound} value={sound}>{sound}</option>)}</select></label></div>}</div><button className="ticon" aria-label="Toggle color theme" onClick={() => setDark(!dark)}>{dark ? <Sun /> : <Moon />}</button><div className="profile"><span className="profile-avatar">DR</span><span><b>Dr. Riley</b><small>Therapist</small></span><ChevronDown size={14}/></div></div>
    </header>
    <div className="tdashboard">
      <section className="tintro"><div><div className="teyebrow">CLIENT OVERVIEW</div><h1>Good morning, Dr. Riley</h1><p>A thoughtful look at your client&apos;s wellbeing, day by day.</p></div><div className="intro-controls"><label className="demo-switch-row"><span><b>Demo mode</b><small>{demo ? 'Fetches every 5 minutes' : 'Daily refresh'}</small></span><button type="button" className={`switch ${demo ? 'on' : ''}`} role="switch" aria-checked={demo} aria-label="Toggle demo mode" onClick={() => setDemo(v => !v)}><i/></button></label><div className="client-select"><span className="client-avatar">JM</span><span><small>SELECTED CLIENT</small><b>Jordan M.</b></span><ChevronDown size={15}/></div></div></section>
      <section className="tstats">
        <article className="stat-card"><span className="stat-label">LATEST DISTRESS INDEX</span><strong>{latest == null ? '—' : latest}<small>{latest == null ? '' : '/100'}</small></strong><span className="stat-note"><Activity size={14}/> {latest == null ? 'No reading available yet' : 'Most recent daily reading'}</span></article>
        <article className="stat-card"><span className="stat-label">PERIOD AVERAGE</span><strong>{periodReadings.length ? Math.round(average) : '—'}<small>{periodReadings.length ? '/100' : ''}</small></strong><span className="stat-note">Across the selected period</span></article>
        <article className="stat-card"><span className="stat-label">REPORT STATUS</span><strong className="report-ready"><span className="status-dot"/>{summary ? 'Ready' : 'Pending'}</strong><span className="stat-note"><Clock3 size={14}/> {summary?.generated_at ? `Updated ${new Date(summary.generated_at).toLocaleDateString()}` : 'Daily report appears after day end'}</span></article>
      </section>
      <section className="panel chart-panel">
        <div className="panel-heading"><div><div className="heading-icon"><Activity size={17}/></div><div><h2>Distress index</h2><p>Daily wellbeing score · lower values indicate less distress</p></div></div><div className="chart-actions"><div className="period-switch"><button className={period === 'week' ? 'selected' : ''} onClick={() => setPeriod('week')}>7 days</button><button className={period === 'month' ? 'selected' : ''} onClick={() => setPeriod('month')}>Month</button></div><button className="refresh-button" onClick={() => void loadReport()} aria-label="Refresh data"><RefreshCw size={15}/></button></div></div>
        <div className="chart-wrap">{hasChartData && <svg viewBox={`0 0 ${chart.W} ${chart.H}`} role="img" aria-label={`${period === 'week' ? '7 day' : 'Monthly'} distress index chart`}>
          {[0,25,50,75,100].map(v => <g key={v}><line x1={chart.left} x2={chart.W-chart.right} y1={chart.y(v)} y2={chart.y(v)} className="grid-line"/><text x="0" y={chart.y(v)+4} className="axis-label">{v}</text></g>)}
          {chart.line && <><path d={chart.line} className="chart-line"/>{chart.entries.map((p,i) => p.value === null ? null : <circle key={i} cx={chart.x(i)} cy={chart.y(p.value)} r="4.5" className="chart-point"><title>{demo ? p.label : p.date.toLocaleDateString()}: {p.value}</title></circle>)}</>}
          {chart.entries.map((p,i) => (period === 'week' || i % 5 === 0 || i === chart.entries.length-1) && <text key={i} x={chart.x(i)} y={chart.H-5} textAnchor="middle" className="axis-label">{demo ? p.label.replace('Demo day ', 'D') : period === 'week' ? p.date.toLocaleDateString(undefined,{weekday:'short'}) : p.date.getDate()}</text>)}
        </svg>}</div>
        <div className="chart-footer"><span><i className="legend-dot"/> Distress index</span><span><CalendarDays size={13}/> {period === 'week' ? 'Last 7 days' : 'Last 30 days'}</span><span>{loading ? 'Updating…' : lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}` : 'Waiting for data'}</span></div>
      </section>
      <section className="lower-grid">
        <article className="panel summary-panel"><div className="panel-heading"><div><div className="heading-icon sparkle">✳</div><div><h2>AI daily summary</h2><p>End of day reflection</p></div></div><span className="generated-tag">{summary ? 'LATEST REPORT' : 'AWAITING REPORT'}</span></div>
          {summary ? <div className="summary-copy"><h3>Daily wellbeing summary</h3><p>{summary.assessment_report ?? 'No assessment report was provided.'}</p>{summary.date && <small>Report date: {summary.date}</small>}</div> : <div className="summary-empty"><span className="summary-icon"><Clock3 size={18}/></span><div><b>Today&apos;s report will appear here</b><p>The report is requested after the day closes. No data is shown until the service returns a reading.</p></div></div>}
          <div className="schedule-note"><span className="schedule-pip"/><span>Daily check at midnight · checks again when this dashboard opens</span></div>
        </article>
      </section>
      <footer className="tfooter"><span><span className="footer-shield">◆</span> Client information is private and secure</span><span>SafeMind · Therapist workspace</span></footer>
    </div>
  </main>
}

function BrainIcon() { return <svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M15.8 7a4 4 0 0 0-7.5 2 4.2 4.2 0 0 0-2.1 7 4.1 4.1 0 0 0 2.2 7 4 4 0 0 0 7.4 1.6V7Zm.4 0a4 4 0 0 1 7.5 2 4.2 4.2 0 0 1 2.1 7 4.1 4.1 0 0 1-2.2 7 4 4 0 0 1-7.4 1.6V7Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/><path d="M11 12.5c1.7 0 2.7 1.1 2.7 2.8M11 20c1.7 0 2.7-1.1 2.7-2.8m7.3-4.7c-1.7 0-2.7 1.1-2.7 2.8m2.7 4.7c-1.7 0-2.7-1.1-2.7-2.8" stroke="currentColor" strokeWidth="1.45" strokeLinecap="round"/></svg> }
