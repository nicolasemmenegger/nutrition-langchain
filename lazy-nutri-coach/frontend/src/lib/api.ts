const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

let TOKEN: string | null = localStorage.getItem('token')

export function setToken(t: string) {
  TOKEN = t
  localStorage.setItem('token', t)
}

async function req(path: string, opts: any = {}) {
  const headers: any = opts.headers || {}
  if (!(opts.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  if (TOKEN) headers['Authorization'] = `Bearer ${TOKEN}`
  const res = await fetch(API + path, { ...opts, headers })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(txt || res.statusText)
  }
  return res.json()
}

export const api = {
  health: () => req('/health'),
  register: (email: string, password: string) => req('/auth/register', {method:'POST', body: JSON.stringify({email, password})}),
  login: (email: string, password: string) => req('/auth/login', {method:'POST', body: JSON.stringify({email, password})}),
  logManual: (items: any[], dayISO?: string, meal_type: string = 'unspecified') => {
    const payload: any = {items, source:'manual', meal_type}
    if (dayISO) payload.timestamp = dayISO
    return req('/foods/log', {method:'POST', body: JSON.stringify(payload)})
  },
  logItems: (items: any[], dayISO?: string, meal_type: string = 'unspecified', source: 'manual'|'text'|'image' = 'manual') => {
    const payload: any = {items, source, meal_type}
    if (dayISO) payload.timestamp = dayISO
    return req('/foods/log', {method:'POST', body: JSON.stringify(payload)})
  },
  parseText: (text: string) => {
    const fd = new FormData()
    fd.append('text', text)
    return req('/foods/parse_text', {method:'POST', body: fd})
  },
  parseTextDraft: (text: string) => {
    const fd = new FormData()
    fd.append('text', text)
    return req('/foods/parse_text_draft', {method:'POST', body: fd})
  },
  textChat: (messages: {role:'user'|'assistant', content:string}[], meal_type?: string, timestamp?: string) => {
    const body: any = {messages}
    if (meal_type) body.meal_type = meal_type
    if (timestamp) body.timestamp = timestamp
    return req('/foods/text_chat', {method:'POST', body: JSON.stringify(body)})
  },
  searchFoods: (q: string) => req(`/foods/search?q=${encodeURIComponent(q)}`),
  getUnits: (name: string) => req(`/foods/units?name=${encodeURIComponent(name)}`),
  parseImage: (file: File, hint?: string) => {
    const fd = new FormData()
    fd.append('file', file)
    if (hint) fd.append('hint', hint)
    return req('/foods/parse_image', {method:'POST', body: fd})
  },
  history: (startISO?: string, endISO?: string) => {
    const params = new URLSearchParams()
    if (startISO) params.set('start', startISO)
    if (endISO) params.set('end', endISO)
    const qs = params.toString()
    return req('/foods/history' + (qs ? `?${qs}` : ''))
  },
  deleteLog: (id: number) => req(`/foods/log/${id}`, {method:'DELETE'}),
  advice: (focus?: string, horizon_days: number = 7) => req('/advice/generate', {method:'POST', body: JSON.stringify({focus, horizon_days})}),
  recipes: (payload: any) => req('/recipes/generate', {method:'POST', body: JSON.stringify(payload)}),
  daily: () => req('/progress/daily_macros'),
}
