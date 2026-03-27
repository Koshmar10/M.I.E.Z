import { useState } from 'react'
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'
import './App.css'
import Sidebar from './components/Sidebar'

type ModulePageProps = {
  title: string
  description: string
}

const ModulePage = ({ title, description }: ModulePageProps) => {
  return (
    <section className="module-card">
      <h2>{title}</h2>
      <p>{description}</p>
    </section>
  )
}

function App() {
  const [unreadNotifications, setUnreadNotifications] = useState(4)

  const handleLogout = () => {
    // Handle logout logic here (clear tokens, redirect, etc.)
    console.log('User logged out')
    // TODO: Implement actual logout logic
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={<Sidebar unreadNotifications={unreadNotifications} onLogout={handleLogout} />}
        >
          <Route path="/" element={<Navigate replace to="/dashboard" />} />
          <Route
            path="/dashboard"
            element={<ModulePage title="Dashboard" description="Overview of your MIEZ platform activity." />}
          />
          <Route
            path="/employees"
            element={<ModulePage title="Register Employees" description="Manage team members and employee records." />}
          />
          <Route
            path="/reports"
            element={<ModulePage title="Reports" description="Review operational and performance insights." />}
          />
          <Route
            path="/workflows"
            element={<ModulePage title="Workflows" description="Automate business processes and tasks." />}
          />
          <Route
            path="/settings"
            element={<ModulePage title="Settings" description="Configure product behavior and account preferences." />}
          />
          <Route
            path="/logout"
            element={<Navigate replace to="/dashboard" />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
