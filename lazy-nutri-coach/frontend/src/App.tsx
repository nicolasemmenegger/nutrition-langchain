import React from 'react'
import { Link, NavLink, Routes, Route } from 'react-router-dom'
import LogPage from './pages/LogPage'
import AdvicePage from './pages/AdvicePage'
import RecipesPage from './pages/RecipesPage'
import ProgressPage from './pages/ProgressPage'
import ProfilePage from './pages/ProfilePage'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="font-bold">Lazy Nutri Coach</div>
          <div className="flex gap-4 text-sm">
            <NavLink to="/" className={({isActive}) => isActive ? 'font-semibold' : ''}>Log</NavLink>
            <NavLink to="/advice" className={({isActive}) => isActive ? 'font-semibold' : ''}>Advice</NavLink>
            <NavLink to="/recipes" className={({isActive}) => isActive ? 'font-semibold' : ''}>Recipes</NavLink>
            <NavLink to="/progress" className={({isActive}) => isActive ? 'font-semibold' : ''}>Progress</NavLink>
            <NavLink to="/profile" className={({isActive}) => isActive ? 'font-semibold' : ''}>Profile</NavLink>
          </div>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto p-4">
        <Routes>
          <Route path="/" element={<LogPage />} />
          <Route path="/advice" element={<AdvicePage />} />
          <Route path="/recipes" element={<RecipesPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Routes>
      </main>
    </div>
  )
}
