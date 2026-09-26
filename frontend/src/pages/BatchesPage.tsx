import { useEffect, useState } from "react";
import { api } from "../api/client";
type P = { id: number; name: string }; type O = { id: number; label: string };
type B = { id: number; code: string; product_name?: string; oven_label?: string; start_min: number; ferment_end?: number; bake_end?: number; status: string };
type PreviewConflict = { opponent_batch_id: number; opponent_code: string; phase: string; opponent_phase: string; interval: string };
type Preview = { start_min: number; ferment_end: number; bake_end: number; overlaps: boolean; conflicts: PreviewConflict[] };
const PHASE_LABEL: Record<string, string> = { ferment: "发酵", bake: "烘烤" };
function fmt(m: number) { const h = Math.floor(m/60), mm = m%60; return `${String(h).padStart(2,"0")}:${String(mm).padStart(2,"0")}`; }
export default function BatchesPage() {
  const [products, setProducts] = useState<P[]>([]);
  const [ovens, setOvens] = useState<O[]>([]);
  const [rows, setRows] = useState<B[]>([]);
  const [pid, setPid] = useState<number | "">(""); const [oid, setOid] = useState<number | "">("");
  const [start, setStart] = useState(11 * 60);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewErr, setPreviewErr] = useState("");
  const [busy, setBusy] = useState<"" | "preview" | "create">("");
  const reload = () => api<B[]>("/batches").then(setRows);
  useEffect(() => {
    api<P[]>("/products").then(p => { setProducts(p); if (p[0]) setPid(p[0].id); });
    api<O[]>("/ovens").then(o => { setOvens(o); if (o[0]) setOid(o[0].id); });
    reload();
  }, []);
  async function previewRun() {
    setBusy("preview"); setPreview(null); setPreviewErr(""); setMsg(""); setErr("");
    try {
      setPreview(await api<Preview>("/batches/preview", { method: "POST", body: JSON.stringify({ product_id: pid, oven_id: oid, start_min: start }) }));
    } catch (e) { setPreviewErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(""); }
  }
  async function create() {
    setBusy("create"); setMsg(""); setErr(""); setPreview(null); setPreviewErr("");
    try {
      const b = await api<B>("/batches", { method: "POST", body: JSON.stringify({ product_id: pid, oven_id: oid, start_min: start }) });
      setMsg(`已创建并排入 ${b.code}（甘特新增发酵、烘烤两段）`);
      reload();
    } catch (e) { setErr(`创建被拒绝：${e instanceof Error ? e.message : String(e)}（已写入冲突日志）`); }
    finally { setBusy(""); }
  }
  return (<>
    <h2>批次</h2>
    <div className="toolbar">
      <select value={pid} onChange={e => setPid(Number(e.target.value))}>{products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <select value={oid} onChange={e => setOid(Number(e.target.value))}>{ovens.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}</select>
      <label>开工分钟 <input type="number" value={start} onChange={e => setStart(Number(e.target.value))} style={{ width: 90 }} /></label>
      <button className="btn-preview" onClick={previewRun} disabled={busy !== ""}>{busy === "preview" ? "试算中…" : "试算"}</button>
      <button onClick={create} disabled={busy !== ""}>{busy === "create" ? "排入中…" : "创建生产批次"}</button>
    </div>

    {preview && (
      <div className={`preview-panel ${preview.overlaps ? "preview-panel--hit" : "preview-panel--ok"}`}>
        <div className="preview-head">
          <span className="preview-tag">试算结果 · 未排入</span>
          <span className={preview.overlaps ? "preview-verdict-hit" : "preview-verdict-ok"}>
            {preview.overlaps ? "存在重叠，若直接创建将被拒绝" : "无重叠，可排入"}
          </span>
        </div>
        <div className="preview-grid">
          <span>若排入后</span>
          <span className="mono">发酵止 {fmt(preview.ferment_end)} ｜ 烘烤止 {fmt(preview.bake_end)}</span>
          <span>重叠阶段 / 对手批次</span>
          <span>
            {preview.overlaps
              ? preview.conflicts.map((c, i) => (
                  <span key={i} className="preview-hit">
                    本批{PHASE_LABEL[c.phase] ?? c.phase} {c.interval} × 对手 <b>{c.opponent_code}</b> 的 {PHASE_LABEL[c.opponent_phase] ?? c.opponent_phase} 段
                  </span>
                ))
              : <span className="muted">—</span>}
          </span>
        </div>
        <div className="preview-note">试算为只读预检：批次表与冲突日志均不变；确认后请点“创建生产批次”。</div>
      </div>
    )}
    {previewErr && <div className="err">试算失败：{previewErr}</div>}

    {msg && <div className="ok">{msg}</div>}
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>批次</th><th>产品</th><th>炉位</th><th>发酵</th><th>烘烤结束</th><th>状态</th></tr></thead>
    <tbody>{rows.map(b => <tr key={b.id}><td className="mono">{b.code}</td><td>{b.product_name}</td><td>{b.oven_label}</td>
      <td className="mono">{fmt(b.start_min)}–{fmt(b.ferment_end ?? b.start_min)}</td>
      <td className="mono">{fmt(b.bake_end ?? b.start_min)}</td><td>{b.status}</td></tr>)}</tbody></table>
  </>);
}
