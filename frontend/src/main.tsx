import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import './index.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
      <Toaster position="top-right" />
    </BrowserRouter>
  </React.StrictMode>
)

if ('serviceWorker' in navigator && window.isSecureContext) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js'))
}
