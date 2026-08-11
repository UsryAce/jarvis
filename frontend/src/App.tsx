import { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { useVoiceStore } from './store/useVoiceStore'
import { useHomeStore } from './store/useHomeStore'
import { useSystemStore } from './store/useSystemStore'
import { TrustBoundary } from './components/trust/TrustBoundary'

const ExactClaudeDesign = lazy(() => import('./pages/ExactClaudeDesign'))
const VoiceChat = lazy(() => import('./pages/VoiceChat').then(module => ({ default: module.VoiceChat })))
const HolographicView = lazy(() => import('./pages/HolographicView').then(module => ({ default: module.HolographicView })))
const VisionDemo = lazy(() => import('./pages/VisionDemo').then(module => ({ default: module.VisionDemo })))
const HomeControl = lazy(() => import('./pages/HomeControl').then(module => ({ default: module.HomeControl })))
const SystemMonitor = lazy(() => import('./pages/SystemMonitor').then(module => ({ default: module.SystemMonitor })))
const Settings = lazy(() => import('./pages/Settings').then(module => ({ default: module.Settings })))

const routeFallback = (
  <div className="jarvis-route-loading" role="status" aria-live="polite">
    <span aria-hidden="true" />
    <strong>JARVIS MODULE HANDOFF</strong>
    <small>Synchronizing interface systems</small>
  </div>
)

function ProtectedApplication() {
  const { initialize: initHome } = useHomeStore()
  const { initialize: initSystem } = useSystemStore()

  useEffect(() => {
    let disposed = false
    const initializeRuntime = async () => {
      // Microphone permission must follow an explicit voice interaction. Asking
      // during dashboard startup breaks remote/mobile sessions that have not
      // granted capture yet and creates duplicate permission prompts.
      await Promise.all([initHome(), initSystem()])
      if (disposed) shutdownProtectedRuntime()
    }
    const shutdownProtectedRuntime = () => {
      const voice = useVoiceStore.getState()
      voice.stopListening()
      voice.stopSpeaking()
      voice.mediaStream?.getTracks().forEach(track => track.stop())
      if (voice.audioContext && voice.audioContext.state !== 'closed') {
        void voice.audioContext.close()
      }
      useVoiceStore.setState({
        audioContext: null,
        mediaStream: null,
        analyser: null,
        transcript: '',
        conversationHistory: [],
      })
      useHomeStore.getState().disconnectMQTT()
      useHomeStore.getState().disconnectHomeAssistant()
      useSystemStore.getState().stopMonitoring()
    }
    void initializeRuntime()
    return () => {
      disposed = true
      shutdownProtectedRuntime()
    }
  }, [initHome, initSystem])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'v' && (e.metaKey || e.ctrlKey)) {
        useVoiceStore.getState().toggleListening()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <div className="app-container">
      <main className="main-content">
        <Suspense fallback={routeFallback}>
          <Routes>
            <Route path="/" element={<ExactClaudeDesign />} />
            <Route path="/mobile" element={<ExactClaudeDesign mobile />} />
            <Route path="/legacy" element={<Dashboard />} />
            <Route path="/voice" element={<VoiceChat />} />
            <Route path="/holographic" element={<HolographicView />} />
            <Route path="/vision" element={<VisionDemo />} />
            <Route path="/home" element={<HomeControl />} />
            <Route path="/system" element={<SystemMonitor />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}

function App() {
  return (
    <TrustBoundary>
      <ProtectedApplication />
    </TrustBoundary>
  )
}

export default App
