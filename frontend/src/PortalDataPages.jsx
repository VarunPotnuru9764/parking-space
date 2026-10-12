import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "./api.js";

function queryString(values) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined) params.set(key, value);
  });
  return params.toString();
}

function dateQuery(startDate, endDate) {
  return {
    start_date: startDate ? `${startDate}T00:00:00` : "",
    end_date: endDate ? `${endDate}T23:59:59.999` : "",
  };
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "—";
}

function money(value) {
  return value == null ? "—" : `₹${Number(value).toFixed(2)}`;
}

function PageHeading({ eyebrow, title, description, action }) {
  return <div className="page-heading"><div><p className="section-kicker">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}

function Notice({ error, success }) {
  return <>{error && <div className="portal-alert" role="alert">{error}</div>}{success && <div className="portal-success" role="status">{success}</div>}</>;
}

function LoadingOrEmpty({ loading, error, empty, onRetry }) {
  if (loading) return <div className="empty-state"><span className="spinner" /> Loading records…</div>;
  if (error) return <div className="empty-state"><strong>Could not load data</strong><span>{error}</span>{onRetry && <button className="button button-outline" onClick={onRetry}>Try again</button>}</div>;
  if (empty) return <div className="empty-state"><strong>No records found</strong><span>There is no matching data for this selection.</span></div>;
  return null;
}

function Table({ columns, rows, empty, loading, error, onRetry }) {
  return <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column.label}>{column.label}</th>)}</tr></thead><tbody>
    {rows.map((row, index) => <tr key={row.key ?? index}>{row.cells.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}
  </tbody></table>{(loading || error || empty) && <LoadingOrEmpty loading={loading} error={error} empty={empty} onRetry={onRetry} />}</div>;
}

function FilterBar({ children, onSubmit }) {
  return <form className="table-tools report-filters" onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>{children}<button className="button button-outline" type="submit">Apply filters</button></form>;
}

function DateFilters({ startDate, endDate, setStartDate, setEndDate }) {
  return <>
    <label className="report-filter-field">From<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
    <label className="report-filter-field">To<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
  </>;
}

function exportCsv(filename, columns, rows) {
  const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const content = [columns.map((column) => quote(column.label)).join(","), ...rows.map((row) => row.values.map(quote).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function MetricCard({ label, value, hint }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>;
}

function ActivityChart({ items, labelKey, valueKey, label }) {
  const maximum = Math.max(1, ...items.map((item) => Number(item[valueKey]) || 0));
  if (!items.length) return <div className="chart-placeholder">No recorded {label.toLowerCase()} data for this range.</div>;
  return <div className="data-chart" role="img" aria-label={label}>
    {items.map((item) => <div className="data-chart-column" key={item[labelKey]} title={`${item[labelKey]}: ${item[valueKey]}`}><span className="data-chart-value">{item[valueKey]}</span><i style={{ height: `${Math.max(5, Number(item[valueKey]) / maximum * 100)}%` }} /><small>{item[labelKey]}</small></div>)}
  </div>;
}

export function ActiveParkingPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const refresh = useCallback(() => {
    setLoading(true);
    apiRequest("/users/me/parking").then((data) => { setItems(data.active_sessions || []); setError(""); }).catch((err) => setError(err.message)).finally(() => setLoading(false));
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  return <div className="page-stack">
    <PageHeading eyebrow="YOUR PARKING" title="My parking" description="Your active parking session and live recorded fare, when available." action={<button className="button button-outline" onClick={refresh}>Refresh</button>} />
    {error && <Notice error={error} />}
    {!loading && !error && !items.length && <section className="panel"><LoadingOrEmpty empty /><p className="muted-paragraph">A session appears here after an occupied space is claimed to your account.</p></section>}
    {items.map((item) => <section className="panel session-detail-card" key={item.history_id}>
      <div className="session-detail-head"><div><span className="live-badge"><i /> ACTIVE SESSION</span><h2>{item.space_id}</h2><p>{item.parking_lot}</p></div><span className="status-pill occupied">Active</span></div>
      <div className="metric-grid session-metrics"><MetricCard label="Arrival recorded" value={formatDate(item.recorded_start)} hint="Detector/session timestamp" /><MetricCard label="Duration" value={`${Number(item.duration_hours || 0).toFixed(2)} hr`} hint="Estimated from the recorded start" /><MetricCard label="Current rate" value={money(item.average_rate)} hint="Average rate recorded so far" /><MetricCard label="Recorded fare" value={money(item.recorded_fare)} hint="Not a payment confirmation" /></div>
      <p className="recorded-time-note">{item.recorded_start_note}</p>
    </section>)}
    {loading && <section className="panel"><LoadingOrEmpty loading /></section>}
  </div>;
}

export function SessionHistoryPage({ lots = [] }) {
  const [filters, setFilters] = useState({ search: "", lot_id: "", start_date: "", end_date: "" });
  const [applied, setApplied] = useState(filters);
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    const params = queryString({ lot_id: applied.lot_id, search: applied.search.trim(), ...dateQuery(applied.start_date, applied.end_date) });
    setLoading(true);
    apiRequest(`/users/me/history?${params}`).then((result) => { setData(result); setError(""); }).catch((err) => setError(err.message)).finally(() => setLoading(false));
  }, [applied]);
  useEffect(() => { load(); }, [load]);
  const columns = [{ label: "LOT" }, { label: "SPACE" }, { label: "ARRIVAL RECORDED" }, { label: "DEPARTURE" }, { label: "DURATION" }, { label: "AVERAGE RATE" }, { label: "RECORDED FARE" }];
  const rows = data.items.map((item) => ({ key: item.history_id, cells: [item.parking_lot, item.space_id, formatDate(item.recorded_start), formatDate(item.departure_time), `${Number(item.duration_hours || 0).toFixed(2)} hr`, money(item.average_rate), money(item.recorded_fare)] }));
  const csvRows = data.items.map((item) => ({ values: [item.parking_lot, item.space_id, item.recorded_start, item.departure_time, item.duration_hours, item.average_rate, item.recorded_fare] }));
  return <div className="page-stack">
    <PageHeading eyebrow="YOUR PARKING" title="Parking history" description="Only sessions associated with your account are shown. Recorded starts may reflect first detector observation." action={<button className="button button-outline" disabled={!rows.length} onClick={() => exportCsv("my-parking-history.csv", columns, csvRows)}>Export CSV</button>} />
    <section className="panel"><FilterBar onSubmit={() => setApplied(filters)}>
      <label className="table-search"><span>⌕</span><input value={filters.search} onChange={(event) => setFilters({ ...filters, search: event.target.value })} placeholder="Search space…" /></label>
      <label className="report-filter-field">Parking lot<select value={filters.lot_id} onChange={(event) => setFilters({ ...filters, lot_id: event.target.value })}><option value="">All lots</option>{lots.map((lot) => <option key={lot.lot_id} value={lot.lot_id}>{lot.name}</option>)}</select></label>
      <DateFilters startDate={filters.start_date} endDate={filters.end_date} setStartDate={(value) => setFilters({ ...filters, start_date: value })} setEndDate={(value) => setFilters({ ...filters, end_date: value })} />
    </FilterBar><div className="records-count">{data.total} session{data.total === 1 ? "" : "s"}</div><Table columns={columns} rows={rows} loading={loading} error={error} empty={!data.items.length} onRetry={load} /></section>
  </div>;
}

function ReportsPage({ admin, lots = [], lotId = "" }) {
  const [filters, setFilters] = useState({ lot_id: lotId || "", start_date: "", end_date: "" });
  const [applied, setApplied] = useState({ lot_id: lotId || "", start_date: "", end_date: "" });
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    if (admin) {
      setFilters((current) => ({ ...current, lot_id: lotId }));
      setApplied((current) => ({ ...current, lot_id: lotId }));
    }
  }, [admin, lotId]);
  const load = useCallback(() => {
    const params = queryString({ lot_id: applied.lot_id, ...dateQuery(applied.start_date, applied.end_date) });
    setLoading(true);
    apiRequest(`${admin ? "/admin/reports" : "/users/me/reports"}?${params}`).then((result) => { setReport(result); setError(""); }).catch((err) => setError(err.message)).finally(() => setLoading(false));
  }, [admin, applied]);
  useEffect(() => { load(); }, [load]);
  const sessions = report?.sessions || [];
  const columns = [{ label: "LOT" }, { label: "SPACE" }, { label: "ARRIVAL RECORDED" }, { label: "DEPARTURE" }, { label: "DURATION" }, { label: "RECORDED FARE" }];
  const rows = sessions.map((item) => ({ key: item.history_id, cells: [item.parking_lot, item.space_id, formatDate(item.recorded_start), formatDate(item.departure_time), `${Number(item.duration_hours || 0).toFixed(2)} hr`, money(item.recorded_fare)] }));
  const csvRows = sessions.map((item) => ({ values: [item.parking_lot, item.space_id, item.recorded_start, item.departure_time, item.duration_hours, item.recorded_fare] }));
  const chartItems = report?.activity_over_time || [];
  const metrics = admin ? [
    ["Parking lots", report?.total_lots ?? "—", "Configured lots"],
    ["Parking spaces", report?.total_spaces ?? "—", `${report?.vacant_spaces ?? 0} vacant`],
    ["Occupancy", report ? `${report.occupancy_percentage}%` : "—", `${report?.occupied_spaces ?? 0} occupied`],
    ["Sessions", report?.total_sessions ?? "—", "In selected date range"],
    ["Recorded charges", money(report?.total_recorded_charges), "Not payment confirmations"],
    ["Recorded duration", `${Number(report?.total_recorded_duration_hours || 0).toFixed(2)} hr`, "Includes active sessions"],
  ] : [
    ["Parking sessions", report?.total_sessions ?? "—", "Associated with your account"],
    ["Recorded duration", `${Number(report?.total_recorded_duration_hours || 0).toFixed(2)} hr`, "In selected date range"],
    ["Recorded charges", money(report?.total_recorded_charges), "Not payment confirmations"],
  ];
  const chartLabel = admin ? "Sessions by day" : "Your sessions by day";
  return <div className="page-stack">
    <PageHeading eyebrow={admin ? "SYSTEM ANALYTICS" : "YOUR PARKING"} title={admin ? "Reports" : "My reports"} description={admin ? "Lot occupancy and session activity with recorded fares, not payments." : "Personal session summaries and recorded charges."} action={<button className="button button-outline" disabled={!sessions.length} onClick={() => exportCsv(admin ? "parking-report.csv" : "my-parking-report.csv", columns, csvRows)}>Export CSV</button>} />
    <section className="panel"><FilterBar onSubmit={() => setApplied(filters)}>
      {lots.length > 0 && <label className="report-filter-field">Parking lot<select value={filters.lot_id} onChange={(event) => setFilters({ ...filters, lot_id: event.target.value })}><option value="">{admin ? "All lots" : "All lots"}</option>{lots.map((lot) => <option key={lot.lot_id} value={lot.lot_id}>{lot.name}</option>)}</select></label>}
      <DateFilters startDate={filters.start_date} endDate={filters.end_date} setStartDate={(value) => setFilters({ ...filters, start_date: value })} setEndDate={(value) => setFilters({ ...filters, end_date: value })} />
    </FilterBar></section>
    {error && <Notice error={error} />}
    <div className={`metric-grid ${admin ? "report-metrics-admin" : ""}`}>{metrics.map(([label, value, hint]) => <MetricCard key={label} label={label} value={loading ? "—" : value} hint={hint} />)}</div>
    {admin && report?.lot_usage && <section className="panel"><h2 className="panel-heading-simple">Usage by lot</h2><div className="lot-usage-list">{report.lot_usage.map((item) => <div key={item.parking_lot}><span>{item.parking_lot}</span><strong>{item.session_count} sessions</strong></div>)}</div></section>}
    <section className="panel report-chart-panel"><div className="panel-title"><div><h2>Activity over time</h2><p>Parking sessions grouped by recorded start date</p></div></div><ActivityChart items={chartItems} labelKey="date" valueKey="session_count" label={chartLabel} /></section>
    {admin && report?.space_usage && <section className="panel"><h2 className="panel-heading-simple">Parking-space usage</h2><div className="lot-usage-list">{report.space_usage.slice(0, 20).map((item) => <div key={item.space}><span>{item.space}</span><strong>{item.session_count} sessions</strong></div>)}</div></section>}
    <section className="panel"><div className="panel-title"><div><h2>Parking sessions</h2><p>{sessions.length} records returned for this report</p></div></div><Table columns={columns} rows={rows} loading={loading} error={error} empty={!sessions.length} onRetry={load} /></section>
  </div>;
}

export function UserReportsPage({ lots, lotId }) { return <ReportsPage admin={false} lots={lots} lotId={lotId} />; }
export function AdminReportsPage({ lots, lotId }) { return <ReportsPage admin lots={lots} lotId={lotId} />; }

export function LoginActivityPage({ admin }) {
  const [filters, setFilters] = useState({ email: "", start_date: "", end_date: "" });
  const [applied, setApplied] = useState(filters);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    const params = queryString({ email: admin ? applied.email.trim() : "", ...dateQuery(applied.start_date, applied.end_date) });
    setLoading(true);
    apiRequest(`${admin ? "/admin/login-activity" : "/users/me/login-activity"}?${params}`).then((data) => { setResult(data); setError(""); }).catch((err) => setError(err.message)).finally(() => setLoading(false));
  }, [admin, applied]);
  useEffect(() => { load(); }, [load]);
  const columns = [{ label: "TIMESTAMP" }, ...(admin ? [{ label: "ACCOUNT" }, { label: "ACTOR" }] : []), { label: "RESULT" }, { label: "CLIENT IP" }, { label: "USER AGENT" }];
  const rows = result.items.map((item) => ({ key: item.event_id, cells: [formatDate(item.timestamp), ...(admin ? [item.account_email || "Unknown", item.actor_user_id ?? "—"] : []), <span className={`status-pill ${item.successful ? "vacant" : "occupied"}`}>{item.successful ? "Successful" : "Failed"}</span>, item.client_ip || "—", item.user_agent || "Not collected"] }));
  const csvRows = result.items.map((item) => ({ values: [item.timestamp, ...(admin ? [item.account_email, item.actor_user_id] : []), item.successful ? "Successful" : "Failed", item.client_ip, item.user_agent] }));
  return <div className="page-stack">
    <PageHeading eyebrow="SECURITY" title={admin ? "Login activity" : "Your login activity"} description={admin ? "Login outcomes and client metadata collected by the API." : "Only sign-in activity associated with your own account is shown."} action={<button className="button button-outline" disabled={!rows.length} onClick={() => exportCsv("login-activity.csv", columns, csvRows)}>Export CSV</button>} />
    <section className="panel"><FilterBar onSubmit={() => setApplied(filters)}>
      {admin && <label className="report-filter-field">Account email<input type="search" value={filters.email} onChange={(event) => setFilters({ ...filters, email: event.target.value })} placeholder="Filter by email" /></label>}
      <DateFilters startDate={filters.start_date} endDate={filters.end_date} setStartDate={(value) => setFilters({ ...filters, start_date: value })} setEndDate={(value) => setFilters({ ...filters, end_date: value })} />
    </FilterBar><div className="records-count">{result.total} login event{result.total === 1 ? "" : "s"}</div><Table columns={columns} rows={rows} loading={loading} error={error} empty={!result.items.length} onRetry={load} /></section>
  </div>;
}

export function AdminUsersPage() {
  const [search, setSearch] = useState("");
  const [applied, setApplied] = useState("");
  const [result, setResult] = useState({ items: [], total: 0 });
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setLoading(true);
    apiRequest(`/admin/users?${queryString({ search: applied })}`).then((data) => { setResult(data); setError(""); }).catch((err) => setError(err.message)).finally(() => setLoading(false));
  }, [applied]);
  useEffect(() => { load(); }, [load]);
  const openUser = async (userId) => {
    setSelected({ loading: true });
    try { setSelected(await apiRequest(`/admin/users/${userId}`)); }
    catch (err) { setSelected({ error: err.message }); }
  };
  const columns = [{ label: "NAME" }, { label: "EMAIL" }, { label: "ROLE" }, { label: "CREATED" }, { label: "SECURITY" }, { label: "" }];
  const rows = result.items.map((item) => ({ key: item.user_id, cells: [item.name, item.email, <span className="code-pill">{item.role}</span>, formatDate(item.created_at), item.mfa_enabled ? "Two-step enabled" : "Standard sign-in", <button className="table-action" onClick={() => openUser(item.user_id)}>Details</button>] }));
  return <div className="page-stack">
    <PageHeading eyebrow="ADMINISTRATION" title="User management" description="Administrator-only account directory. This backend supports viewing accounts, not editing roles or status." />
    <section className="panel"><div className="table-tools"><label className="table-search"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name or email…" /></label><button className="button button-outline" onClick={() => setApplied(search)}>Search</button></div>
      <div className="records-count">{result.total} accounts</div><Table columns={columns} rows={rows} loading={loading} error={error} empty={!result.items.length} onRetry={load} />
    </section>
    {selected && <section className="panel"><div className="panel-title"><div><h2>Account details</h2><p>Read-only account and security information</p></div><button className="button button-text" onClick={() => setSelected(null)}>Close</button></div>{selected.loading ? <LoadingOrEmpty loading /> : selected.error ? <Notice error={selected.error} /> : <div className="detail-list"><div><span>Name</span><strong>{selected.name}</strong></div><div><span>Email</span><strong>{selected.email}</strong></div><div><span>Role</span><strong>{selected.role}</strong></div><div><span>Created</span><strong>{formatDate(selected.created_at)}</strong></div><div><span>Two-step verification</span><strong>{selected.mfa_enabled ? "Enabled" : "Not enabled"}</strong></div></div>}</section>}
  </div>;
}

export function AdminActivityPage() {
  const [filters, setFilters] = useState({ event_type: "", start_date: "", end_date: "" });
  const [applied, setApplied] = useState(filters);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    const params = queryString({ event_type: applied.event_type, ...dateQuery(applied.start_date, applied.end_date) });
    setLoading(true);
    apiRequest(`/admin/activity?${params}`).then((data) => { setResult(data); setError(""); }).catch((err) => setError(err.message)).finally(() => setLoading(false));
  }, [applied]);
  useEffect(() => { load(); }, [load]);
  const columns = [{ label: "TIME" }, { label: "EVENT" }, { label: "DESCRIPTION" }, { label: "ACTOR" }, { label: "RESULT" }, { label: "CLIENT" }];
  const rows = result.items.map((item) => ({ key: item.event_id, cells: [formatDate(item.timestamp), <span className="code-pill">{item.event_type}</span>, item.description, item.account_email || item.actor_user_id || "System", <span className={`status-pill ${item.successful ? "vacant" : "occupied"}`}>{item.successful ? "OK" : "Failed"}</span>, item.client_ip || "—"] }));
  const csvRows = result.items.map((item) => ({ values: [item.timestamp, item.event_type, item.description, item.account_email || item.actor_user_id || "System", item.successful, item.client_ip] }));
  return <div className="page-stack">
    <PageHeading eyebrow="SYSTEM AUDIT" title="Activity logs" description="Events recorded by the application API. No server files are read by the browser." action={<button className="button button-outline" disabled={!rows.length} onClick={() => exportCsv("parking-activity.csv", columns, csvRows)}>Export CSV</button>} />
    <section className="panel"><FilterBar onSubmit={() => setApplied(filters)}>
      <label className="report-filter-field">Event type<input value={filters.event_type} onChange={(event) => setFilters({ ...filters, event_type: event.target.value })} placeholder="e.g. parking.claim_confirmed" /></label>
      <DateFilters startDate={filters.start_date} endDate={filters.end_date} setStartDate={(value) => setFilters({ ...filters, start_date: value })} setEndDate={(value) => setFilters({ ...filters, end_date: value })} />
    </FilterBar><div className="records-count">{result.total} events</div><Table columns={columns} rows={rows} loading={loading} error={error} empty={!result.items.length} onRetry={load} /></section>
  </div>;
}

const emptyRule = { rule_name: "", base_rate: "", min_occupancy: "0", max_occupancy: "100", occupancy_multiplier: "1", peak_multiplier: "1", start_time: "", end_time: "" };

export function FareRulesPage({ lots = [], lotId = "" }) {
  const [selectedLot, setSelectedLot] = useState(lotId || "");
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState(emptyRule);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (lotId) setSelectedLot(lotId); }, [lotId]);
  const load = useCallback(() => {
    if (!selectedLot) { setRules([]); setLoading(false); return; }
    setLoading(true);
    apiRequest(`/admin/fare-rules?lot_id=${encodeURIComponent(selectedLot)}`).then((data) => { setRules(data); setError(""); }).catch((err) => setError(err.message)).finally(() => setLoading(false));
  }, [selectedLot]);
  useEffect(() => { load(); }, [load]);
  const startEdit = (rule) => {
    setEditing(rule.rule_id);
    setForm({ rule_name: rule.rule_name, base_rate: String(rule.base_rate), min_occupancy: String(rule.min_occupancy), max_occupancy: String(rule.max_occupancy), occupancy_multiplier: String(rule.occupancy_multiplier), peak_multiplier: String(rule.peak_multiplier), start_time: rule.start_time?.slice(0, 5) || "", end_time: rule.end_time?.slice(0, 5) || "" });
    setMessage(""); setError("");
  };
  const submit = async (event) => {
    event.preventDefault();
    if (!selectedLot) return;
    setBusy(true); setError(""); setMessage("");
    const payload = {
      rule_name: form.rule_name.trim(),
      base_rate: Number(form.base_rate),
      min_occupancy: Number(form.min_occupancy),
      max_occupancy: Number(form.max_occupancy),
      occupancy_multiplier: Number(form.occupancy_multiplier),
      peak_multiplier: Number(form.peak_multiplier),
      start_time: form.start_time || null,
      end_time: form.end_time || null,
    };
    try {
      await apiRequest(editing ? `/admin/fare-rules/${editing}` : "/admin/fare-rules", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(editing ? payload : { lot_id: Number(selectedLot), ...payload }),
      });
      setForm(emptyRule); setEditing(null); setMessage(editing ? "Fare rule updated." : "Fare rule created."); await load();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const columns = [{ label: "RULE" }, { label: "BASE RATE" }, { label: "OCCUPANCY BAND" }, { label: "MULTIPLIERS" }, { label: "TIME RANGE" }, { label: "ENGINE STATE" }, { label: "" }];
  const rows = rules.map((rule) => ({ key: rule.rule_id, cells: [rule.rule_name, `${money(rule.base_rate)} / hr`, `${rule.min_occupancy}% – ${rule.max_occupancy}%`, `Occupancy ×${rule.occupancy_multiplier} · Peak ×${rule.peak_multiplier}`, rule.start_time ? `${rule.start_time} – ${rule.end_time}` : "All day", rule.active ? "Active" : "Inactive", <button className="table-action" onClick={() => startEdit(rule)}>Edit</button>] }));
  return <div className="page-stack">
    <PageHeading eyebrow="PRICING CONFIGURATION" title="Fare rules" description="Rules follow the existing fare engine. Active state is managed by the scheduler and cannot be edited here." />
    <section className="panel fare-rule-panel"><div className="panel-title"><div><h2>Rules for selected lot</h2><p>Only non-overlapping occupancy bands are accepted by the backend.</p></div><label className="report-filter-field">Parking lot<select value={selectedLot} onChange={(event) => { setSelectedLot(event.target.value); setEditing(null); }}><option value="">Select a lot</option>{lots.map((lot) => <option key={lot.lot_id} value={lot.lot_id}>{lot.name}</option>)}</select></label></div>
      <Notice error={error} success={message} />
      <form className="fare-rule-form" onSubmit={submit}><h3>{editing ? "Edit fare rule" : "Create fare rule"}</h3><div className="form-row fare-form-grid">
        <label>Rule name<input required maxLength={100} value={form.rule_name} onChange={(event) => setForm({ ...form, rule_name: event.target.value })} /></label>
        <label>Base rate / hour<input required type="number" min="0.01" step="0.01" value={form.base_rate} onChange={(event) => setForm({ ...form, base_rate: event.target.value })} /></label>
        <label>Minimum occupancy %<input required type="number" min="0" max="100" step="0.01" value={form.min_occupancy} onChange={(event) => setForm({ ...form, min_occupancy: event.target.value })} /></label>
        <label>Maximum occupancy %<input required type="number" min="0" max="100" step="0.01" value={form.max_occupancy} onChange={(event) => setForm({ ...form, max_occupancy: event.target.value })} /></label>
        <label>Occupancy multiplier<input required type="number" min="0.01" step="0.01" value={form.occupancy_multiplier} onChange={(event) => setForm({ ...form, occupancy_multiplier: event.target.value })} /></label>
        <label>Peak multiplier<input required type="number" min="0.01" step="0.01" value={form.peak_multiplier} onChange={(event) => setForm({ ...form, peak_multiplier: event.target.value })} /></label>
        <label>Peak start time<input type="time" value={form.start_time} onChange={(event) => setForm({ ...form, start_time: event.target.value })} /></label>
        <label>Peak end time<input type="time" value={form.end_time} onChange={(event) => setForm({ ...form, end_time: event.target.value })} /></label>
      </div><div className="fare-form-actions"><button className="button button-primary" disabled={busy || !selectedLot}>{busy ? "Saving…" : editing ? "Save changes" : "Create rule"}</button>{editing && <button type="button" className="button button-outline" onClick={() => { setEditing(null); setForm(emptyRule); }}>Cancel edit</button>}</div></form>
      <Table columns={columns} rows={rows} loading={loading} error={error} empty={!rules.length} onRetry={load} />
    </section>
  </div>;
}

export function PasswordResetPage({ token, onComplete }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const submit = async (event) => {
    event.preventDefault(); setError(""); setSuccess("");
    if (!token) { setError("This reset link is missing its token. Request a new password reset."); return; }
    if (password !== confirm) { setError("The passwords do not match."); return; }
    setBusy(true);
    try {
      const result = await apiRequest("/auth/password-reset/complete", { method: "POST", body: JSON.stringify({ token, new_password: password }) });
      setSuccess(result.message || "Password reset successfully."); onComplete();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <form className="auth-form" onSubmit={submit}>
    <label>New password<input type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
    <label>Confirm new password<input type="password" autoComplete="new-password" required minLength={8} maxLength={72} value={confirm} onChange={(event) => setConfirm(event.target.value)} /></label>
    <Notice error={error} success={success} />
    <button className="button button-primary full-width" disabled={busy}>{busy ? "Resetting…" : "Reset password"}</button>
  </form>;
}

export function PasswordResetRequestForm() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const submit = async (event) => {
    event.preventDefault(); setError(""); setMessage(""); setBusy(true);
    try {
      const result = await apiRequest("/auth/password-reset/request", { method: "POST", body: JSON.stringify({ email: email.trim() }) });
      setMessage(result.message);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <form className="auth-form" onSubmit={submit}><label>Email address<input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></label><Notice error={error} success={message} /><button className="button button-primary full-width" disabled={busy}>{busy ? "Sending…" : "Send reset link"}</button></form>;
}

export function MfaVerificationForm({ challenge, onVerified }) {
  const [code, setCode] = useState("");
  const [resendAfter, setResendAfter] = useState(challenge?.resend_after || 0);
  const [expiresIn, setExpiresIn] = useState(challenge?.expires_in || 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const timer = window.setInterval(() => {
      setResendAfter((value) => Math.max(0, value - 1));
      setExpiresIn((value) => Math.max(0, value - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);
  const submit = async (event) => {
    event.preventDefault(); setError("");
    if (!challenge?.challenge_token) { setError("Verification session is missing. Please sign in again."); return; }
    setBusy(true);
    try {
      const result = await apiRequest("/auth/mfa/verify", { method: "POST", body: JSON.stringify({ challenge_token: challenge.challenge_token, code }) });
      onVerified(result.access_token);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const resend = async () => {
    setError(""); setBusy(true);
    try {
      await apiRequest("/auth/mfa/resend", { method: "POST", body: JSON.stringify({ challenge_token: challenge.challenge_token }) });
      setResendAfter(challenge.resend_after || 30); setExpiresIn(challenge.expires_in || 300);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <form className="auth-form" onSubmit={submit}>
    <p className="muted-paragraph">Enter the six-digit code sent to your account email. Code expires in <strong>{Math.floor(expiresIn / 60)}:{String(expiresIn % 60).padStart(2, "0")}</strong>.</p>
    <label>Verification code<input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" /></label>
    {error && <Notice error={error} />}
    <button className="button button-primary full-width" disabled={busy || expiresIn <= 0}>{busy ? "Verifying…" : "Verify and sign in"}</button>
    <button className="button button-outline full-width" type="button" disabled={busy || resendAfter > 0} onClick={resend}>{resendAfter > 0 ? `Resend code in ${resendAfter}s` : "Resend code"}</button>
    {expiresIn <= 0 && <small className="form-help">This code has expired. Resend a code to continue.</small>}
  </form>;
}

export function AccountSecuritySettings({ user, onLogout }) {
  const [passwords, setPasswords] = useState({ current_password: "", new_password: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [mfaChallenge, setMfaChallenge] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [disableChallenge, setDisableChallenge] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [enabled, setEnabled] = useState(Boolean(user.mfa_enabled));
  const [resendAfter, setResendAfter] = useState(0);
  useEffect(() => {
    if (!resendAfter) return undefined;
    const timer = window.setTimeout(() => setResendAfter((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [resendAfter]);
  const updatePassword = async (event) => {
    event.preventDefault(); setError(""); setMessage("");
    if (passwords.new_password !== passwords.confirm) { setError("The new passwords do not match."); return; }
    setBusy(true);
    try {
      const result = await apiRequest("/users/me/password", { method: "PUT", body: JSON.stringify({ current_password: passwords.current_password, new_password: passwords.new_password }) });
      setMessage(result.message); setPasswords({ current_password: "", new_password: "", confirm: "" });
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const startMfa = async () => {
    setError(""); setMessage(""); setBusy(true);
    try {
      const result = await apiRequest("/auth/mfa/setup", { method: "POST" });
      setMfaChallenge(result.challenge_token); setMessage(result.message); setResendAfter(30);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const enableMfa = async (event) => {
    event.preventDefault(); setError(""); setMessage(""); setBusy(true);
    try {
      const result = await apiRequest("/auth/mfa/enable", { method: "POST", body: JSON.stringify({ challenge_token: mfaChallenge, code: mfaCode }) });
      setEnabled(Boolean(result.mfa_enabled)); setMfaChallenge(""); setMfaCode(""); setMessage(result.message);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const requestDisable = async () => {
    setError(""); setMessage(""); setBusy(true);
    try {
      const result = await apiRequest("/auth/mfa/disable/request", { method: "POST" });
      setDisableChallenge(result.challenge_token); setMessage(result.message); setResendAfter(30);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const disableMfa = async (event) => {
    event.preventDefault(); setError(""); setMessage(""); setBusy(true);
    try {
      const result = await apiRequest("/auth/mfa", { method: "DELETE", body: JSON.stringify({ challenge_token: disableChallenge, code: disableCode, current_password: passwords.current_password }) });
      setEnabled(Boolean(result.mfa_enabled)); setDisableChallenge(""); setDisableCode(""); setMessage(result.message);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <div className="page-stack">
    <PageHeading eyebrow="ACCOUNT" title="Profile & settings" description="Your account information, password and email-based two-step verification." />
    <Notice error={error} success={message} />
    <div className="content-grid settings-grid">
      <section className="panel profile-panel"><div className="panel-title"><div><h2>Account information</h2><p>Details returned by your authenticated profile</p></div></div><div className="detail-list"><div><span>Full name</span><strong>{user.name}</strong></div><div><span>Email address</span><strong>{user.email}</strong></div><div><span>Account role</span><strong>{user.role}</strong></div><div><span>Created</span><strong>{formatDate(user.created_at)}</strong></div></div><p className="muted-paragraph">Profile name and email editing are not provided by the backend.</p><a className="button button-outline" href="#/app/login-activity">View my login activity</a></section>
      <section className="panel security-panel"><div className="panel-title"><div><h2>Change password</h2><p>Confirm your current password before saving</p></div></div><form className="settings-form" onSubmit={updatePassword}><label>Current password<input type="password" autoComplete="current-password" required value={passwords.current_password} onChange={(event) => setPasswords({ ...passwords, current_password: event.target.value })} /></label><label>New password<input type="password" autoComplete="new-password" minLength={8} maxLength={72} required value={passwords.new_password} onChange={(event) => setPasswords({ ...passwords, new_password: event.target.value })} /></label><label>Confirm new password<input type="password" autoComplete="new-password" minLength={8} maxLength={72} required value={passwords.confirm} onChange={(event) => setPasswords({ ...passwords, confirm: event.target.value })} /></label><button className="button button-primary" disabled={busy}>{busy ? "Saving…" : "Update password"}</button></form></section>
      <section className="panel security-panel"><div className="panel-title"><div><h2>Two-step verification</h2><p>Email code verification at sign-in</p></div><span className={`status-pill ${enabled ? "vacant" : "unknown"}`}>{enabled ? "Enabled" : "Disabled"}</span></div>
        {!enabled && !mfaChallenge && <><p className="muted-paragraph">A one-time code will be emailed when you sign in. Email delivery must be configured by the administrator.</p><button className="button button-outline" disabled={busy} onClick={startMfa}>{busy ? "Requesting…" : "Enable two-step verification"}</button></>}
        {mfaChallenge && <form className="settings-form" onSubmit={enableMfa}><label>Verification code<input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={mfaCode} onChange={(event) => setMfaCode(event.target.value.replace(/\D/g, "").slice(0, 6))} /></label><button className="button button-primary" disabled={busy}>Verify and enable</button><small className="form-help">Code expires in five minutes. {resendAfter ? `Resend available in ${resendAfter}s.` : ""}</small></form>}
        {enabled && !disableChallenge && <button className="button button-outline" disabled={busy} onClick={requestDisable}>Request code to disable</button>}
        {disableChallenge && <form className="settings-form" onSubmit={disableMfa}><label>Current password<input type="password" autoComplete="current-password" required value={passwords.current_password} onChange={(event) => setPasswords({ ...passwords, current_password: event.target.value })} /></label><label>Verification code<input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={disableCode} onChange={(event) => setDisableCode(event.target.value.replace(/\D/g, "").slice(0, 6))} /></label><button className="button button-primary" disabled={busy}>Verify and disable</button><small className="form-help">Code expires in five minutes.</small></form>}
      </section>
      <section className="panel security-panel"><div className="panel-title"><div><h2>Account session</h2><p>End this browser session</p></div></div><button className="button button-outline logout-settings" onClick={onLogout}>Sign out</button></section>
    </div>
  </div>;
}
