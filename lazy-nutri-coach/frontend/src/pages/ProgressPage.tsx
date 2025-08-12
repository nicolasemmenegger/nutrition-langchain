import React, { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend, ResponsiveContainer } from 'recharts'

export default function ProgressPage() {
  const [days, setDays] = useState<any[]>([])

  useEffect(() => {
    api.daily().then(res => setDays(res.days || [])).catch(console.error)
  }, [])

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Daily Macros</h2>
      <div className="bg-white border rounded p-4">
        <div className="w-full h-[360px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={days}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="calories" />
              <Line type="monotone" dataKey="protein" />
              <Line type="monotone" dataKey="carbs" />
              <Line type="monotone" dataKey="fat" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
