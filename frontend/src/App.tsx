import { useEffect, useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'

function App() {
  useEffect(() => {
    fetch('/api/health/')
      .then(r => r.json())
      .then(data => console.log(data))  // → {status: "ok"}
  }, [])
  return (
    <>
      <div>

        <p>Denis e un homosexual a iesit la date cu un baiat</p>
      </div>

    </>
  )
}

export default App
