import { useEffect, useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'
import Sidebar from './components/Sidebar'

function App() {
  useEffect(() => {
    fetch('/api/health/')
      .then(r => r.json())
      .then(data => console.log(data))  // → {status: "ok"}
  }, [])
  return (
    <>
      <div>
        <Sidebar />
        <h1 className="text-3xl font-bold text-blue-500">MIEZ</h1>
      </div>

    </>
  )
}

export default App
