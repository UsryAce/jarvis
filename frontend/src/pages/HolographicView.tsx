import React, { useState, useEffect, useRef } from 'react'
import * as THREE from 'three'
import { useVoiceStore } from '../store/useVoiceStore'
import { useVisionStore } from '../store/useVisionStore'
import { useSystemStore } from '../store/useSystemStore'

export const HolographicView: React.FC = () => {
  const { isListening, isSpeaking, isProcessing, wakeWordDetected, transcript, confidence } = useVoiceStore()
  const { latestResult, isCameraActive } = useVisionStore()
  const { cpuUsage, gpu } = useSystemStore()
  const [time, setTime] = useState(new Date())
  const [showOverlay, setShowOverlay] = useState(true)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'o' || e.key === 'O') setShowOverlay(prev => !prev)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  useEffect(() => {
    if (!canvasRef.current) return
    const canvas = canvasRef.current
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x050510)

    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000)
    camera.position.z = 8

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: false, antialias: true })
    renderer.setSize(window.innerWidth, window.innerHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

    const particleCount = 3000
    const positions = new Float32Array(particleCount * 3)
    const colors = new Float32Array(particleCount * 3)
    const sizes = new Float32Array(particleCount)
    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 50
      positions[i * 3 + 1] = (Math.random() - 0.5) * 30
      positions[i * 3 + 2] = (Math.random() - 0.5) * 50
      const hue = 0.55 + Math.random() * 0.15
      const col = new THREE.Color().setHSL(hue, 1, 0.5)
      colors[i * 3] = col.r; colors[i * 3 + 1] = col.g; colors[i * 3 + 2] = col.b
      sizes[i] = Math.random() * 3 + 0.5
    }

    const particleGeo = new THREE.BufferGeometry()
    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    particleGeo.setAttribute('size', new THREE.BufferAttribute(sizes, 1))
    const particleMat = new THREE.PointsMaterial({
      size: 0.15, vertexColors: true, transparent: true, opacity: 0.7,
      sizeAttenuation: true, blending: THREE.AdditiveBlending,
      depthWrite: false
    })
    const particles = new THREE.Points(particleGeo, particleMat)
    scene.add(particles)

    const ringGroup = new THREE.Group()
    const ringConfigs = [
      { radius: 1.8, color: '#00ffff', speed: 0.4, opacity: 0.25 },
      { radius: 2.4, color: '#ff00ff', speed: -0.3, opacity: 0.2 },
      { radius: 3.0, color: '#ff6b00', speed: 0.2, opacity: 0.15 },
      { radius: 1.2, color: '#00ff88', speed: 0.6, opacity: 0.2 },
    ]
    ringConfigs.forEach(cfg => {
      const geo = new THREE.RingGeometry(cfg.radius * 0.92, cfg.radius, 80)
      const mat = new THREE.MeshBasicMaterial({
        color: cfg.color, transparent: true, opacity: cfg.opacity,
        side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false
      })
      const mesh = new THREE.Mesh(geo, mat)
      mesh.rotation.x = Math.PI / 2
      mesh.position.y = Math.sin(Math.random() * Math.PI * 2) * 0.5
      mesh.userData = { speed: cfg.speed, phase: Math.random() * Math.PI * 2 }
      ringGroup.add(mesh)
    })
    scene.add(ringGroup)

    const dotGeo = new THREE.BufferGeometry()
    const dotPos = new Float32Array(60 * 3)
    for (let i = 0; i < 60; i++) {
      const angle = (i / 60) * Math.PI * 2
      dotPos[i * 3] = Math.cos(angle) * 2.1
      dotPos[i * 3 + 1] = Math.sin(angle) * 0.3
      dotPos[i * 3 + 2] = Math.sin(angle) * 2.1
    }
    dotGeo.setAttribute('position', new THREE.BufferAttribute(dotPos, 3))
    const dotMat = new THREE.PointsMaterial({
      size: 0.08, color: '#00ffff', transparent: true, opacity: 0.6,
      blending: THREE.AdditiveBlending
    })
    const dotRing = new THREE.Points(dotGeo, dotMat)
    scene.add(dotRing)

    const coreLight = new THREE.PointLight('#00ffff', 1, 15)
    coreLight.position.set(0, 0, 0)
    scene.add(coreLight)
    const coreLight2 = new THREE.PointLight('#ff00ff', 0.5, 15)
    coreLight2.position.set(2, 1, -1)
    scene.add(coreLight2)

    const ambient = new THREE.AmbientLight('#222244', 0.3)
    scene.add(ambient)

    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)')
    let reduceMotion = motionPreference.matches
    const handleMotionPreference = (event: MediaQueryListEvent) => { reduceMotion = event.matches }
    motionPreference.addEventListener('change', handleMotionPreference)
    let animationFrame = 0
    let frame = 0
    let previousVoiceMode = ''
    const animate = () => {
      animationFrame = requestAnimationFrame(animate)
      frame++
      const voice = useVoiceStore.getState()
      const data = voice.audioData
      let energy = 0
      for (let index = 0; index < data.length; index++) {
        const magnitude = data[index] / 255
        energy += magnitude * magnitude
      }
      const measuredLevel = data.length ? Math.sqrt(energy / data.length) : 0
      const deterministicSpeech = voice.isSpeaking && !reduceMotion
        ? 0.28 + Math.sin(frame * 0.17) * 0.12
        : 0
      const audioLevel = Math.min(1, Math.max(measuredLevel, deterministicSpeech))
      const voiceMode = voice.isListening ? 'listening' : voice.isSpeaking ? 'speaking' : voice.isProcessing ? 'processing' : 'idle'
      const motionScale = voice.isSpeaking ? 2 : voice.isListening ? 1.45 : voice.isProcessing ? 1.1 : 0.5

      if (voiceMode !== previousVoiceMode) {
        const primary = voice.isSpeaking ? '#ffb733' : voice.isProcessing ? '#9270ff' : '#00ffff'
        const secondary = voice.isSpeaking ? '#ff6b00' : voice.isListening ? '#00ff88' : '#ff00ff'
        coreLight.color.set(primary)
        coreLight2.color.set(secondary)
        dotMat.color.set(primary)
        previousVoiceMode = voiceMode
      }

      if (!reduceMotion) {
        particles.rotation.y += 0.0003 * motionScale
        particles.rotation.x = Math.sin(frame * 0.0002 * motionScale) * 0.05
      }

      ringGroup.children.forEach((mesh, i) => {
        const cfg = ringConfigs[i]
        if (!reduceMotion) {
          mesh.rotation.z += cfg.speed * 0.01 * motionScale
          mesh.position.y = Math.sin(frame * 0.008 * motionScale + i * 1.5) * 0.3
        }
        const mat = mesh as THREE.Mesh
        if (mat.material) {
          const m = mat.material as THREE.MeshBasicMaterial
          m.opacity = cfg.opacity * (reduceMotion ? 0.8 : 0.6 + Math.sin(frame * 0.02 * motionScale + i) * 0.4)
        }
      })

      if (!reduceMotion) {
        dotRing.rotation.y += 0.005 * motionScale
        dotRing.rotation.x = Math.sin(frame * 0.003 * motionScale) * 0.1
      }

      coreLight.intensity = 1 + audioLevel * 2 + (voice.isListening ? 0.35 : 0)
      coreLight2.intensity = 0.5 + audioLevel + (voice.isSpeaking ? 0.3 : 0)
      particles.material.opacity = 0.5 + audioLevel * 0.3

      if (!reduceMotion && voice.isListening) {
        camera.position.z = 7 + Math.sin(frame * 0.01) * 0.5
      } else {
        camera.position.z += (8 - camera.position.z) * 0.02
      }
      camera.lookAt(0, 0, 0)

      renderer.render(scene, camera)
    }
    animate()

    const handleResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight
      camera.updateProjectionMatrix()
      renderer.setSize(window.innerWidth, window.innerHeight)
    }
    window.addEventListener('resize', handleResize)

    return () => {
      cancelAnimationFrame(animationFrame)
      window.removeEventListener('resize', handleResize)
      motionPreference.removeEventListener('change', handleMotionPreference)
      scene.traverse(object => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Points) {
          object.geometry.dispose()
          const materials = Array.isArray(object.material) ? object.material : [object.material]
          materials.forEach(material => material.dispose())
        }
      })
      renderer.renderLists.dispose()
      renderer.dispose()
      renderer.forceContextLoss()
    }
  }, [])

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: '#050510', overflow: 'hidden', fontFamily: "'JetBrains Mono', monospace" }}>
      <canvas ref={canvasRef} style={{ position: 'fixed', inset: 0, width: '100%', height: '100%' }} />

      {showOverlay && (
        <>
          <header style={{
            position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
            padding: '15px 30px',
            background: 'linear-gradient(180deg, rgba(5,5,16,0.95) 0%, transparent 100%)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{
                fontSize: '20px', fontWeight: '700', letterSpacing: '4px',
                background: 'linear-gradient(135deg, #00ffff, #ff00ff, #ff6b00)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text'
              }}>HOLOGRAPHIC</div>
              <div style={{ display: 'flex', gap: '12px', fontSize: '11px', opacity: 0.6 }}>
                <span>CPU: <span style={{ color: cpuUsage > 70 ? '#ff00ff' : '#00ffff' }}>{cpuUsage.toFixed(1)}%</span></span>
                <span>GPU: <span style={{ color: gpu[0]?.usage > 70 ? '#ff00ff' : '#ff6b00' }}>{gpu[0]?.usage.toFixed(1) || 0}%</span></span>
              </div>
            </div>
            <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#00ffff', textShadow: '0 0 10px #00ffff' }}>
              {time.toLocaleTimeString()}
            </div>
          </header>

          <div style={{
            position: 'fixed', bottom: '30px', left: '50%', transform: 'translateX(-50%)', zIndex: 100,
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '15px',
            maxWidth: '600px', width: '90%'
          }}>
            <div style={{
              padding: '12px 24px', borderRadius: '12px',
              background: 'rgba(5,5,16,0.9)', backdropFilter: 'blur(20px)',
              border: `1px solid ${wakeWordDetected ? '#ff00ff' : isListening ? '#00ffff' : 'rgba(0,255,255,0.2)'}`,
              boxShadow: `0 0 30px ${wakeWordDetected ? 'rgba(255,0,255,0.3)' : 'rgba(0,255,255,0.15)'}`,
              textAlign: 'center', width: '100%'
            }}>
              <div style={{ fontSize: '11px', opacity: 0.7, marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '2px' }}>
                <span style={{ color: wakeWordDetected ? '#ff00ff' : isListening ? '#00ffff' : '#888' }}>
                  {wakeWordDetected ? 'Wake Word Detected' : isListening ? 'Listening' : isSpeaking ? 'Speaking' : isProcessing ? 'Processing' : 'Standby'}
                </span>
                <span style={{ marginLeft: '12px', opacity: 0.5 }}>Confidence: {(confidence * 100).toFixed(0)}%</span>
              </div>
              <div style={{ fontSize: '15px', color: '#e6e8f0', minHeight: '24px', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                {transcript || 'Say "Jarvis" to activate...'}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={() => { const s = useVoiceStore.getState(); s.isListening ? s.stopListening() : s.startListening() }}
                style={{
                  padding: '12px 24px', borderRadius: '8px', border: 'none', cursor: 'pointer',
                  fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', fontWeight: '600',
                  textTransform: 'uppercase', letterSpacing: '1px',
                  background: isListening ? 'linear-gradient(135deg, #ff0000, #ff6b00)' : 'linear-gradient(135deg, #00ffff, #0088ff)',
                  color: '#000', boxShadow: `0 0 20px ${isListening ? 'rgba(255,0,0,0.4)' : 'rgba(0,255,255,0.4)'}`
                }}
              >{isListening ? 'STOP' : 'LISTEN'}</button>
              <button
                onClick={() => { useVoiceStore.getState().speak('JARVIS holographic display active. All systems online.') }}
                style={{
                  padding: '12px 24px', borderRadius: '8px', border: 'none', cursor: 'pointer',
                  fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', fontWeight: '600',
                  textTransform: 'uppercase', letterSpacing: '1px',
                  background: 'linear-gradient(135deg, #ff00ff, #8800ff)', color: '#fff',
                  boxShadow: '0 0 20px rgba(255,0,255,0.4)'
                }}
              >TEST VOICE</button>
            </div>
          </div>

          <div style={{
            position: 'fixed', right: '20px', top: '50%', transform: 'translateY(-50%)', zIndex: 100,
            display: 'flex', flexDirection: 'column', gap: '10px'
          }}>
            {['#00ffff', '#ff00ff', '#ff6b00', '#00ff88'].map((color, i) => (
              <div key={i} style={{
                width: '8px', height: '8px', borderRadius: '50%',
                background: color, boxShadow: `0 0 15px ${color}`,
                opacity: 0.5 + (isListening ? Math.sin(Date.now() * 0.003 + i) * 0.3 : 0),
                transition: 'opacity 0.3s'
              }} />
            ))}
          </div>

          <div style={{
            position: 'fixed', left: '20px', top: '50%', transform: 'translateY(-50%)', zIndex: 100,
            display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '10px', color: '#888'
          }}>
            <StatusLabel label="PARTICLES" value="3,000" color="#00ffff" />
            <StatusLabel label="RINGS" value="4" color="#ff00ff" />
            <StatusLabel label="CAMERA" value={isCameraActive ? 'ACTIVE' : 'OFF'} color={isCameraActive ? '#00ff00' : '#888'} />
            <StatusLabel label="VISION" value={latestResult ? 'DATA' : 'WAIT'} color={latestResult ? '#00ff00' : '#888'} />
          </div>
        </>
      )}

      <style>{`
        @keyframes pulse { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:0.7; transform:scale(1.05); } }
        ::-webkit-scrollbar { width:6px; }
        ::-webkit-scrollbar-track { background:#050510; }
        ::-webkit-scrollbar-thumb { background:linear-gradient(180deg,#00ffff,#ff00ff); border-radius:3px; }
        body { margin:0; overflow:hidden; }
      `}</style>
    </div>
  )
}

const StatusLabel: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
    <span style={{ opacity: 0.5, textTransform: 'uppercase', letterSpacing: '1px' }}>{label}</span>
    <span style={{ color, fontWeight: '600' }}>{value}</span>
  </div>
)

export default HolographicView
