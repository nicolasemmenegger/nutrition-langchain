import React, { useState } from 'react'
import { api } from '../lib/api'

export default function RecipesPage() {
  const [dietary, setDietary] = useState('dairy-free')
  const [kcal, setKcal] = useState(500)
  const [time, setTime] = useState(20)
  const [have, setHave] = useState('chickpeas, cucumber, tomato')
  const [out, setOut] = useState<any[]>([])

  async function run() {
    const res = await api.recipes({
      dietary, target_calories: Number(kcal)||undefined, time_limit_min: Number(time)||undefined,
      available_ingredients: have ? have.split(',').map(s=>s.trim()) : undefined
    })
    setOut(res.recipes || [])
  }

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-4 gap-2 items-center">
        <input className="border px-2 py-1 rounded" value={dietary} onChange={e=>setDietary(e.target.value)} placeholder="Dietary (optional)" />
        <input className="border px-2 py-1 rounded" type="number" value={kcal} onChange={e=>setKcal(Number(e.target.value))} placeholder="Target kcal" />
        <input className="border px-2 py-1 rounded" type="number" value={time} onChange={e=>setTime(Number(e.target.value))} placeholder="Time (min)" />
        <input className="border px-2 py-1 rounded" value={have} onChange={e=>setHave(e.target.value)} placeholder="Available ingredients (comma-separated)" />
      </div>
      <button className="bg-black text-white px-3 py-1 rounded" onClick={run}>Suggest</button>

      <div className="grid md:grid-cols-2 gap-4">
        {out.map((r, i) => (
          <div key={i} className="bg-white border rounded p-4">
            <div className="font-semibold">{r.name}</div>
            <div className="text-sm text-gray-600">{r.est_kcal} kcal • {r.time_min} min</div>
            <div className="mt-2">
              <div className="font-medium">Ingredients</div>
              <ul className="list-disc ml-5 text-sm">
                {r.ingredients.map((ing:string, idx:number) => <li key={idx}>{ing}</li>)}
              </ul>
            </div>
            <div className="mt-2">
              <div className="font-medium">Steps</div>
              <ol className="list-decimal ml-5 text-sm">
                {r.steps.map((s:string, idx:number) => <li key={idx}>{s}</li>)}
              </ol>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
