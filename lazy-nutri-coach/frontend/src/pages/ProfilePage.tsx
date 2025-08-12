import React, { useState } from 'react'
import { api, setToken } from '../lib/api'

export default function ProfilePage() {
  const [email, setEmail] = useState('demo@example.com')
  const [password, setPassword] = useState('demo1234')
  const [token, setTok] = useState<string | null>(localStorage.getItem('token'))

  async function login() {
    const tok = await api.login(email, password)
    // @ts-ignore
    const t = tok.access_token
    setToken(t)
    setTok(t)
  }

  return (
    <div className="space-y-4">
      <div className="text-sm text-gray-600">Manage your session token for API calls.</div>
      <div className="flex gap-2">
        <input className="border px-2 py-1 rounded" value={email} onChange={e=>setEmail(e.target.value)} placeholder="Email" />
        <input className="border px-2 py-1 rounded" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Password" />
        <button className="bg-black text-white px-3 py-1 rounded" onClick={login}>Login</button>
      </div>
      {token ? <div className="text-xs break-all">Token: {token}</div> : <div className="text-xs">No token</div>}
    </div>
  )
}
