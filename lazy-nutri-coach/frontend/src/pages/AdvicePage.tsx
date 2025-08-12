import React, { useState } from 'react'
import { api } from '../lib/api'

export default function AdvicePage() {
  const [focus, setFocus] = useState('protein')
  const [days, setDays] = useState(7)
  const [text, setText] = useState('')

  async function run() {
    const res = await api.advice(focus, days)
    setText(res.text)
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center">
        <input className="border px-2 py-1 rounded" value={focus} onChange={e=>setFocus(e.target.value)} placeholder="Focus (optional)" />
        <input className="border px-2 py-1 rounded w-24" type="number" value={days} onChange={e=>setDays(Number(e.target.value))} />
        <button className="bg-black text-white px-3 py-1 rounded" onClick={run}>Generate</button>
      </div>
      {text && (
        <div className="bg-white border rounded p-4 whitespace-pre-wrap">{text}</div>
      )}
      <p className="text-xs text-gray-500">Educational use only — not medical advice.</p>
    </div>
  )
}
