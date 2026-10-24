import { useEffect, useRef, useState } from 'react'
import './StudentPicker.css'

// selected: [{student_id, name}]   onChange(newSelected)   search(q) -> Promise<[{student_id, name}]>
export default function StudentPicker({ selected, onChange, search, max = Infinity, allowCustom = false }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const box = useRef(null)
  const chosen = new Set(selected.map((s) => s.student_id))

  useEffect(() => {
    if (!open) return
    let live = true
    setLoading(true)
    const t = setTimeout(async () => {
      try {
        const rows = await search(q.trim())
        if (live) setResults(Array.isArray(rows) ? rows : [])
      } catch { if (live) setResults([]) }
      finally { if (live) setLoading(false) }
    }, 250)
    return () => { live = false; clearTimeout(t) }
  }, [q, open])

  useEffect(() => {
    const close = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const fresh = results.filter((r) => !chosen.has(r.student_id))
  const add = (rows) => { onChange([...selected, ...rows.map((r) => ({ student_id: r.student_id, name: r.name }))].slice(0, max)); setQ('') }
  const full = selected.length >= max
  const typed = q.trim().toUpperCase()
  const canCustom = allowCustom && typed && !results.some((r) => r.student_id.toUpperCase() === typed) && !chosen.has(typed)
  const remove = (id) => onChange(selected.filter((s) => s.student_id !== id))

  return (
    <div className="sp" ref={box}>
      <div className="sp-head">
        <span>{selected.length}{Number.isFinite(max) ? `/${max}` : ''} student{selected.length === 1 ? '' : 's'} selected</span>
        {selected.length > 0 && <button type="button" className="sp-clear" onClick={() => onChange([])}>Clear all</button>}
      </div>
      {selected.length > 0 && (
        <div className="sp-chips">
          {selected.map((s) => (
            <span className="sp-chip" key={s.student_id}>
              {s.student_id}{s.name ? ` · ${s.name}` : ''}
              <button type="button" aria-label={`Remove ${s.student_id}`} onClick={() => remove(s.student_id)}>×</button>
            </span>
          ))}
        </div>
      )}
      <input className="sp-input" value={q} disabled={full} placeholder={full ? `Limit of ${max} reached` : 'Type a name or an ID, for example Abebe or ST004…'}
             onFocus={() => setOpen(true)} onChange={(e) => { setQ(e.target.value); setOpen(true) }}
             onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (fresh[0]) add([fresh[0]]); else if (canCustom) add([{ student_id: typed, name: '' }]) } }} />
      {open && !full && (
        <div className="sp-list">
          {loading && <div className="sp-note">Searching…</div>}
          {!loading && fresh.length === 0 && !canCustom && <div className="sp-note">{results.length ? 'Everyone found is already added' : 'No students found'}</div>}
          {!loading && fresh.length > 1 && (
            <button type="button" className="sp-all" onClick={() => add(fresh)}>Add all {fresh.length} results</button>
          )}
          {!loading && canCustom && fresh.length === 0 && (
            <button type="button" className="sp-row" onClick={() => add([{ student_id: typed, name: '' }])}>Use ID <b>{typed}</b> (not registered)</button>
          )}
          {fresh.map((r) => (
            <button type="button" className="sp-row" key={r.student_id} onClick={() => add([r])}>
              <b>{r.student_id}</b><span>{r.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
