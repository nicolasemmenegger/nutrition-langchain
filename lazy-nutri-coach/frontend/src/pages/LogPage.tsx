import React, { useEffect, useState } from 'react'
import { api, setToken } from '../lib/api'

type Item = { name: string, grams: number, calories: number, protein: number, carbs: number, fat: number, unit?: string, amount?: number }
type MealType = 'breakfast' | 'lunch' | 'snacks' | 'dinner' | 'unspecified'
type ChatMessage = { role: 'user' | 'assistant'; content: string }

export default function LogPage() {
  const [email, setEmail] = useState('demo@example.com')
  const [password, setPassword] = useState('demo1234')
  const [items, setItems] = useState<Item[]>([
    {name:'Greek yogurt', grams:150, calories:0, protein:0, carbs:0, fat:0},
  ])
  const [text, setText] = useState('chicken breast 200g, rice 150g, olive oil 10g')
  const [textDraftItems, setTextDraftItems] = useState<Item[] | null>(null)
  const [confirmSuggestions, setConfirmSuggestions] = useState<Record<number, any[]>>({})
  const [confirming, setConfirming] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [hint, setHint] = useState('Here is my lunch bowl from a salad bar.')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {role:'assistant', content:'Tell me what you ate. I will estimate quantities and ask you to confirm.'}
  ])
  const [history, setHistory] = useState<any[]>([])
  const [msg, setMsg] = useState<string>('')
  const [selectedDay, setSelectedDay] = useState<string>(new Date().toISOString())
  const [mealType, setMealType] = useState<MealType>('unspecified')

  useEffect(() => {
    api.health().catch(console.error)
    // If a token already exists from a previous session, ensure api uses it
    const existing = localStorage.getItem('token')
    if (existing) setToken(existing)
  }, [])

  async function doRegister() {
    try {
      await api.register(email, password)
    } catch (e) {
      // ignore if already registered; proceed to login
    }
    const tok = await api.login(email, password)
    // @ts-ignore
    if (tok?.access_token) setToken(tok.access_token)
    setMsg('Signed in!')
    await refreshHistory()
  }

  async function doLogin() {
    try {
      const tok = await api.login(email, password)
      // @ts-ignore
      if (tok?.access_token) setToken(tok.access_token)
      setMsg('Signed in!')
      await refreshHistory()
    } catch (err:any) {
      setMsg(err?.message || 'Login failed')
    }
  }

  async function refreshHistory() {
    try {
      const end = new Date()
      const start = new Date()
      start.setDate(end.getDate() - 30)
      const h = await api.history(start.toISOString(), end.toISOString())
      setHistory(h)
    } catch (err:any) {
      setMsg(err?.message || 'Failed to load history (are you signed in?)')
    }
  }

  async function logManual() {
    try {
      await api.logManual(items, selectedDay, mealType)
      setMsg('Logged manual entry.')
      await refreshHistory()
    } catch (err:any) {
      setMsg(err?.message || 'Failed to log entry')
    }
  }

  async function parseTextDraft() {
    try {
      const res = await api.parseTextDraft(text)
      setTextDraftItems(res.items)
      setConfirming(true)
      setMsg('Please confirm the parsed items before logging.')
    } catch (err:any) {
      setMsg(err?.message || 'Failed to parse text')
    }
  }

  async function confirmAndLogText() {
    if (!textDraftItems) return
    try {
      await api.logItems(textDraftItems, selectedDay, mealType, 'text')
      setMsg('Logged from text.')
      setConfirming(false)
      setTextDraftItems(null)
      await refreshHistory()
    } catch (err:any) {
      setMsg(err?.message || 'Failed to log parsed items')
    }
  }

  async function sendChatMessage(msg: string) {
    const msgs: ChatMessage[] = [...chatMessages, {role:'user', content: msg}]
    setChatMessages(msgs)
    try {
      const res = await api.textChat(msgs, mealType, selectedDay)
      setChatMessages(prev => [...msgs, {role:'assistant', content: res.assistant_text as string}])
      if (res.items && res.items.length > 0 && res.needs_confirmation) {
        // prefill draft confirm editor with items if user wants to adjust manually
        setTextDraftItems(res.items)
        setConfirming(true)
      }
      if (res.logged) {
        setMsg('Logged from chat.')
        await refreshHistory()
      }
    } catch (err:any) {
      setMsg(err?.message || 'Failed to send chat message')
    }
  }

  async function logImage() {
    if (!file) return
    const res = await api.parseImage(file, hint)
    setMsg('Logged from image.')
    refreshHistory()
  }

  function updateItem(i: number, patch: Partial<Item>) {
    setItems(prev => prev.map((it, idx) => idx===i ? {...it, ...patch} : it))
  }

  return (
    <div className="grid md:grid-cols-2 gap-6">
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">1) Sign up / Sign in</h2>
        <div className="flex gap-2">
          <input className="border px-2 py-1 rounded w-full" value={email} onChange={e=>setEmail(e.target.value)} placeholder="Email" />
          <input className="border px-2 py-1 rounded" value={password} type="password" onChange={e=>setPassword(e.target.value)} placeholder="Password" />
          <button className="bg-black text-white px-3 py-1 rounded" onClick={doLogin}>Login</button>
          <button className="bg-gray-800 text-white px-3 py-1 rounded" onClick={doRegister}>Register</button>
        </div>

        <h2 className="text-xl font-semibold mt-6">2) Manual log</h2>
        <div className="flex gap-2 items-center text-sm">
          <label>Date/Time</label>
          <input type="datetime-local" className="border px-2 py-1 rounded" value={new Date(selectedDay).toISOString().slice(0,16)} onChange={e=>{
            const val = e.target.value
            // interpret as local datetime -> ISO
            const dt = new Date(val)
            setSelectedDay(dt.toISOString())
          }} />
          <label>Meal</label>
          <select className="border px-2 py-1 rounded" value={mealType} onChange={e=>setMealType(e.target.value as MealType)}>
            <option value="breakfast">Breakfast</option>
            <option value="lunch">Lunch</option>
            <option value="snacks">Snacks</option>
            <option value="dinner">Dinner</option>
            <option value="unspecified">Unspecified</option>
          </select>
        </div>
        <div className="space-y-2">
          {items.map((it, i) => (
            <FoodRow key={i} item={it} onChange={(patch)=>updateItem(i,patch)} />
          ))}
          <div className="flex gap-2">
            <button className="text-sm underline" onClick={()=>setItems(prev=>[...prev,{name:'',grams:100, calories:0, protein:0, carbs:0, fat:0}])}>+ add</button>
            <button className="bg-blue-600 text-white px-3 py-1 rounded" onClick={logManual}>Log</button>
          </div>
        </div>

        <h2 className="text-xl font-semibold mt-6">3) Text log</h2>
        <textarea className="border w-full min-h-[80px] p-2 rounded text-sm" value={text} onChange={e=>setText(e.target.value)} />
        <div className="flex gap-2 items-center">
          <button className="bg-blue-600 text-white px-3 py-1 rounded" onClick={parseTextDraft}>Parse</button>
          {confirming && (
            <>
              <button className="bg-green-600 text-white px-3 py-1 rounded" onClick={confirmAndLogText}>Confirm & Log</button>
              <button className="border px-3 py-1 rounded" onClick={()=>{setConfirming(false); setTextDraftItems(null)}}>Cancel</button>
            </>
          )}
        </div>
        {confirming && textDraftItems && (
          <div className="mt-2 text-sm">
            <div className="font-medium mb-1">Parsed items (you can adjust before logging):</div>
            <div className="space-y-2">
              {textDraftItems.map((it, idx)=> (
                <div key={idx} className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <input
                      className="border px-2 py-1 rounded w-48"
                      value={it.name}
                      onChange={e=>{
                        const v = e.target.value
                        setTextDraftItems(prev => prev ? prev.map((p,i)=> i===idx ? {...p, name: v} : p) : prev)
                      }}
                    />
                    <button
                      className="text-xs underline"
                      onClick={async()=>{
                        try {
                          const res = await api.searchFoods(textDraftItems[idx].name)
                          setConfirmSuggestions(prev => ({...prev, [idx]: res}))
                        } catch {}
                      }}
                    >Find match</button>
                    <input
                      className="border px-2 py-1 rounded w-24"
                      type="number"
                      value={it.grams}
                      onChange={e=>{
                        const v = Number(e.target.value)
                        setTextDraftItems(prev => prev ? prev.map((p,i)=> i===idx ? {...p, grams: v} : p) : prev)
                      }}
                    />
                    <span>g</span>
                  </div>
                  {confirmSuggestions[idx]?.length > 0 && (
                    <div className="border rounded bg-white shadow-sm text-xs max-h-32 overflow-auto">
                      {confirmSuggestions[idx].map((s:any, i:number)=> (
                        <div key={i} className="px-2 py-1 hover:bg-gray-100 cursor-pointer flex justify-between" onClick={()=>{
                          setTextDraftItems(prev => prev ? prev.map((p,j)=> j===idx ? {...p, name: s.name} : p) : prev)
                        }}>
                          <span>{s.name}</span>
                          <span className="text-gray-500">{s.calories} kcal/100g</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <h2 className="text-xl font-semibold mt-6">4) Chat log (OpenAI)</h2>
        <div className="border rounded p-2 h-64 overflow-auto bg-white text-sm flex flex-col gap-2">
          {chatMessages.map((m, i)=>(
            <div key={i} className={m.role==='assistant'?'text-gray-800':'text-blue-800'}>
              <span className="font-medium mr-1">{m.role==='assistant'?'Coach':'You'}:</span>
              <span>{m.content}</span>
            </div>
          ))}
        </div>
        <div className="flex gap-2 mt-2">
          <input className="border px-2 py-1 rounded w-full" placeholder="Type your message..." onKeyDown={e=>{
            if (e.key==='Enter') {
              const val = (e.target as HTMLInputElement).value
              if (val.trim().length>0){
                ;(e.target as HTMLInputElement).value = ''
                sendChatMessage(val)
              }
            }
          }} />
          <button className="bg-blue-600 text-white px-3 py-1 rounded" onClick={()=>{
            const input = document.querySelector<HTMLInputElement>('input[placeholder="Type your message..."]')
            const val = input?.value || ''
            if (val.trim().length>0){
              if (input) input.value = ''
              sendChatMessage(val)
            }
          }}>Send</button>
        </div>

        <h2 className="text-xl font-semibold mt-6">5) Image log (needs OpenAI key on backend)</h2>
        <input type="file" onChange={e=>setFile(e.target.files?.[0] || null)} />
        <input className="border px-2 py-1 rounded w-full mt-2" value={hint} onChange={e=>setHint(e.target.value)} placeholder="Optional hint, e.g., 'Sweetgreen bowl'" />
        <button className="bg-blue-600 text-white px-3 py-1 rounded mt-2" onClick={logImage}>Parse & Log</button>

        {msg && <p className="text-green-700 text-sm mt-2">{msg}</p>}
      </div>

      <div>
        <h2 className="text-xl font-semibold">Last 30 Days</h2>
        <Calendar history={history} onSelect={(iso)=>setSelectedDay(iso)} onDelete={async(id)=>{await api.deleteLog(id); await refreshHistory()}} />
      </div>
    </div>
  )
}

function dayISO(date: Date) {
  const d = new Date(date)
  d.setHours(0,0,0,0)
  return d.toISOString()
}

function groupByDayAndMeal(entries: any[]) {
  const by: Record<string, Record<string, any[]>> = {}
  for (const e of entries) {
    const d = dayISO(new Date(e.timestamp))
    by[d] ||= {breakfast:[], lunch:[], snacks:[], dinner:[], unspecified:[]}
    by[d][e.meal_type || 'unspecified'].push(e)
  }
  return by
}

function Calendar({history, onSelect, onDelete}:{history:any[], onSelect:(iso:string)=>void, onDelete:(id:number)=>Promise<void>}){
  const by = groupByDayAndMeal(history)
  const today = new Date()
  const days: Date[] = []
  for (let i=0;i<30;i++){
    const d = new Date(today)
    d.setDate(today.getDate()-i)
    days.push(d)
  }
  return (
    <div className="grid md:grid-cols-2 gap-4">
      {days.map(d=>{
        const iso = dayISO(d)
        const meals = by[iso] || {breakfast:[], lunch:[], snacks:[], dinner:[], unspecified:[]}
        return (
          <div key={iso} className="bg-white border rounded p-3 text-sm">
            <div className="flex justify-between items-center">
              <div className="font-medium">{d.toDateString()}</div>
              <button className="text-xs underline" onClick={()=>onSelect(new Date(d).toISOString())}>Log here</button>
            </div>
            {(['breakfast','lunch','snacks','dinner','unspecified'] as MealType[]).map(m => (
              <div key={m} className="mt-2">
                <div className="font-medium capitalize">{m}</div>
                {meals[m].length === 0 ? (
                  <div className="text-gray-500 text-xs">No entries</div>
                ) : (
                  <ul className="list-disc ml-5">
                    {meals[m].map((h:any)=> (
                      <li key={h.id}>
                        <span className="text-gray-600 mr-1">[{new Date(h.timestamp).toLocaleTimeString()}]</span>
                        {h.items.map((it:any, idx:number) => (
                          <span key={idx}>{it.name} {it.grams}g{idx<h.items.length-1?', ':''}</span>
                        ))}
                        <button className="ml-2 text-red-600 text-xs" onClick={()=>onDelete(h.id)}>Delete</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}

function FoodRow({item, onChange}:{item:Item, onChange:(patch:Partial<Item>)=>void}){
  const [query, setQuery] = useState(item.name)
  const [suggestions, setSuggestions] = useState<any[]>([])
  const [units, setUnits] = useState<{[k:string]: number}>({g:1})
  const [useUnits, setUseUnits] = useState(false)
  const [amountInput, setAmountInput] = useState<string>(item.amount != null ? String(item.amount) : '1')
  const [amountValid, setAmountValid] = useState<boolean>(true)
  useEffect(()=>{
    let active = true
    if (query.trim().length === 0){ setSuggestions([]); return }
    const t = setTimeout(async()=>{
      try {
        const res = await api.searchFoods(query)
        if (active) setSuggestions(res)
      } catch { /* ignore */ }
    }, 200)
    return ()=>{ active = false; clearTimeout(t) }
  },[query])

  // If user toggles to unit mode and we only have default units, try to load units for the current query
  useEffect(()=>{
    if (!useUnits) return
    const onlyG = Object.keys(units).length === 1 && units.g === 1
    if (onlyG && query.trim().length > 0) {
      api.getUnits(query).then(u=>{
        setUnits(u)
        const first = Object.keys(u)[0] || 'g'
        if (!item.unit) onChange({unit:first, amount: item.amount ?? 1})
      }).catch(()=>{})
    } else {
      // ensure defaults present
      const first = Object.keys(units)[0] || 'g'
      if (!item.unit) onChange({unit:first, amount: item.amount ?? 1})
    }
  }, [useUnits])

  function parseFractionString(s: string): number | null {
    const str = s.trim()
    if (!str) return null
    // handle mixed number like "1 1/2"
    if (/^\d+\s+\d+\/\d+$/.test(str)) {
      const [whole, frac] = str.split(/\s+/)
      const [n,d] = frac.split('/').map(Number)
      if (!d) return null
      return Number(whole) + n/d
    }
    // handle simple fraction like "1/2"
    if (/^\d+\/\d+$/.test(str)) {
      const [n,d] = str.split('/').map(Number)
      if (!d) return null
      return n/d
    }
    // fallback to decimal
    const v = Number(str)
    return isNaN(v) ? null : v
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex gap-2 text-sm items-center">
        <input className="border px-2 py-1 rounded w-40" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search food" />
        {useUnits ? (
          <>
            <input
              className={`border px-2 py-1 rounded w-24 ${amountValid ? '' : 'border-red-500'}`}
              value={amountInput}
              onChange={e=>{
                const val = e.target.value
                setAmountInput(val)
                const parsed = parseFractionString(val)
                if (parsed == null) {
                  setAmountValid(false)
                } else {
                  setAmountValid(true)
                  onChange({amount: parsed})
                }
              }}
              placeholder="e.g. 1/2"
            />
            <select className="border px-2 py-1 rounded" value={item.unit || 'g'} onChange={e=>onChange({unit:e.target.value})}>
              {Object.keys(units).map(u=> <option key={u} value={u}>{u}</option>)}
            </select>
          </>
        ) : (
          <>
            <input className="border px-2 py-1 rounded w-24" type="number" value={item.grams} onChange={e=>onChange({grams:Number(e.target.value)})} />
            <span>g</span>
          </>
        )}
        <button className="text-xs underline" onClick={()=>setUseUnits(v=>!v)}>{useUnits?'Use grams':'Use units'}</button>
      </div>
      {suggestions.length>0 && (
        <div className="border rounded bg-white shadow-sm max-h-40 overflow-auto text-sm">
          {suggestions.map((s:any, idx:number)=> (
            <div key={idx} className="px-2 py-1 hover:bg-gray-100 cursor-pointer" onClick={()=>{
              onChange({
                name: s.name,
                // set default 100g macros; backend will recompute precise values
                calories: s.calories,
                protein: s.protein,
                carbs: s.carbs,
                fat: s.fat,
              })
              setQuery(s.name)
              setSuggestions([])
              api.getUnits(s.name).then(u=>{
                setUnits(u)
                const first = Object.keys(u)[0] || 'g'
                onChange({unit:first, amount: item.amount ?? 1})
              }).catch(()=>setUnits({g:1}))
              setUseUnits(true)
            }}>
              <div className="flex justify-between">
                <span>{s.name}</span>
                <span className="text-gray-500">{s.calories} kcal/100g</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
