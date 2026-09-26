import { useEffect, useState } from "react";
import { api } from "../api/client";
type P = { id: number; name: string }; type O = { id: number; label: string };
type B = { id: number; code: string; product_name?: string; oven_label?: string; start_min: number; ferment_end?: number; bake_end?: number; status: string };
type TrialConflict = { batch_id: number; code: string; phase: string; existing_start: number; existing_end: number; candidate_phase: string; candidate_start: number; candidate_end: number };
type Trial = { would_overlap: boolean; phases: string[]; opponents: string[]; ferment_end: number; bake_end: number; conflicts: TrialConflict[] };
function fmt(m: number) { const h = Math.floor(m/60), mm = m%60; return `${String(h).padStart(2,"0")}:${String(mm).padStart(2,"0")}`; }
function phaseLabel(p: string) { return p === "ferment" ? "发酵" : "烘烤"; }
export default function BatchesPage() {
  const [products, setProducts] = useState<P[]>([]);
  const [ovens, setOvens] = useState<O[]>([]);
  const [rows, setRows] = useState<B[]>([]);
  const [pid, setPid] = useState<number | "">(""); const [oid, setOid] = useState<number | "">("");
  const [start, setStart] = useState(11 * 60); const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const [trial, setTrial] = useState<Trial | null>(null); const [trialErr, setTrialErr] = useState("");
  const reload = () => api<B[]>("/batches").then(setRows);
  useEffect(() => {
    api<P[]>("/products").then(p => { setProducts(p); if (p[0]) setPid(p[0].id); });
    api<O[]>("/ovens").then(o => { setOvens(o); if (o[0]) setOid(o[0].id); });
    reload();
  }, []);
  const payload = () => JSON.stringify({ product_id: pid, oven_id: oid, start_min: start });
  async function runTrial() {
    setTrial(null); setTrialErr(""); setMsg(""); setErr("");
    try {
      const t = await api<Trial>("/batches/trial", { method: "POST", body: payload() });
      setTrial(t);
    } catch (e) { setTrialErr(e instanceof Error ? e.message : String(e)); }
  }
  async function create() {
    setMsg(""); setErr(""); setTrial(null); setTrialErr("");
    try {
      const b = await api<B>("/batches", { method: "POST", body: payload() });
      setMsg(`已排产 ${b.code}`);
      reload();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }
  return (<>
    <h2>批次</h2>
    <div className="toolbar">
      <select value={pid} onChange={e => setPid(Number(e.target.value))}>{products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <select value={oid} onChange={e => setOid(Number(e.target.value))}>{ovens.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}</select>
      <label>开工分钟 <input type="number" value={start} onChange={e => setStart(Number(e.target.value))} style={{ width: 90 }} /></label>
      <button onClick={runTrial} className="btn-trial">试算</button>
      <button onClick={create}>创建生产批次</button>
    </div>
    {trialErr && <div className="err">试算失败：{trialErr}</div>}
    {trial && (
      <div className={`trial-panel ${trial.would_overlap ? "trial-panel--hit" : "trial-panel--ok"}`}>
        <div className="trial-panel-head">试算结果（未排入）</div>
        <div className="trial-panel-grid">
          <span>是否重叠</span><b>{trial.would_overlap ? "会重叠" : "不重叠"}</b>
          <span>重叠阶段</span><b>{trial.phases.length ? trial.phases.map(phaseLabel).join("、") : "—"}</b>
          <span>对手批次</span><b className="mono">{trial.opponents.length ? trial.opponents.join("、") : "—"}</b>
          <span>若排入</span><b className="mono">发酵止 {fmt(trial.ferment_end)} ・ 烘烤止 {fmt(trial.bake_end)}</b>
        </div>
        {trial.conflicts.length > 0 && (
          <ul className="trial-hits">
            {trial.conflicts.map((c, i) => (
              <li key={i} className="mono">
                {c.code} 的{phaseLabel(c.phase)}段 [{fmt(c.existing_start)}–{fmt(c.existing_end)})
                ← 试算{phaseLabel(c.candidate_phase)}段 [{fmt(c.candidate_start)}–{fmt(c.candidate_end)})
              </li>
            ))}
          </ul>
        )}
      </div>
    )}
    {msg && <div className="ok">创建结果：{msg}</div>}
    {err && <div className="err">创建结果：{err}</div>}
    <table className="table"><thead><tr><th>批次</th><th>产品</th><th>炉位</th><th>发酵</th><th>烘烤结束</th><th>状态</th></tr></thead>
    <tbody>{rows.map(b => <tr key={b.id}><td className="mono">{b.code}</td><td>{b.product_name}</td><td>{b.oven_label}</td>
      <td className="mono">{fmt(b.start_min)}–{fmt(b.ferment_end ?? b.start_min)}</td>
      <td className="mono">{fmt(b.bake_end ?? b.start_min)}</td><td>{b.status}</td></tr>)}</tbody></table>
  </>);
}
