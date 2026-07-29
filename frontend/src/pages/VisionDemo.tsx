import React, { useState, useEffect, useRef } from 'react'
import { useVisionStore } from '../store/useVisionStore'
import { useSystemStore } from '../store/useSystemStore'

export const VisionDemo: React.FC = () => {
  const {
    isCameraActive, latestResult, currentMode, cameraIndex,
    detectionConfidence, trackingConfidence, error, isProcessing,
    startCamera, stopCamera, setMode, setCameraIndex
  } = useVisionStore()
  const { cpuUsage } = useSystemStore()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [detectObjects, setDetectObjects] = useState(false)
  const [availableCameras, setAvailableCameras] = useState<MediaDeviceInfo[]>([])
  const [fps, setFps] = useState(0)
  const frameCountRef = useRef(0)
  const lastFpsTimeRef = useRef(Date.now())

  useEffect(() => {
    navigator.mediaDevices.enumerateDevices().then(devices => {
      setAvailableCameras(devices.filter(d => d.kind === 'videoinput'))
    })
  }, [])

  useEffect(() => {
    if (isCameraActive && videoRef.current && latestResult?.timestamp) {
      videoRef.current.srcObject = useVisionStore.getState().cameraStream
    }
  }, [isCameraActive, latestResult])

  useEffect(() => {
    const fpsInterval = setInterval(() => {
      const now = Date.now()
      const dt = now - lastFpsTimeRef.current
      setFps(Math.round((frameCountRef.current / dt) * 1000))
      frameCountRef.current = 0
      lastFpsTimeRef.current = now
    }, 1000)
    return () => clearInterval(fpsInterval)
  }, [])

  useEffect(() => {
    frameCountRef.current++
  })

  const handleToggleCamera = () => {
    if (isCameraActive) {
      stopCamera()
    } else {
      startCamera(cameraIndex)
    }
  }

  const modes: { key: typeof currentMode; label: string; color: string }[] = [
    { key: 'all', label: 'All', color: '#00ffff' },
    { key: 'face', label: 'Face', color: '#00ff88' },
    { key: 'hands', label: 'Hands', color: '#ff00ff' },
    { key: 'pose', label: 'Pose', color: '#ff6b00' },
    { key: 'objects', label: 'Objects', color: '#ffff00' },
  ]

  return (
    <div style={{
      width: '100%', height: '100%', display: 'flex', flexDirection: 'column',
      background: 'linear-gradient(135deg, #050510 0%, #0a0a1a 100%)',
      fontFamily: "'JetBrains Mono', monospace", color: '#e6e8f0', overflow: 'hidden'
    }}>
      <header style={{
        padding: '15px 30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'rgba(5,5,15,0.95)', backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(0,255,255,0.2)', zIndex: 10
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <h1 style={{
            fontSize: '24px', fontWeight: '700', letterSpacing: '4px',
            background: 'linear-gradient(135deg, #00ffff, #ff00ff)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text'
          }}>VISION</h1>
          <div style={{ display: 'flex', gap: '12px', fontSize: '12px', opacity: 0.7 }}>
            <span>FPS: <strong style={{ color: fps > 20 ? '#00ff00' : '#ff6b00' }}>{fps}</strong></span>
            <span>|</span>
            <span>Mode: <strong style={{ color: '#00ffff' }}>{currentMode.toUpperCase()}</strong></span>
            <span>|</span>
            <span>Tracking: <strong style={{ color: trackingConfidence > 0.5 ? '#00ff00' : '#888' }}>{(trackingConfidence * 100).toFixed(0)}%</strong></span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {error && <span style={{ fontSize: '11px', color: '#ff0000', padding: '4px 12px', background: 'rgba(255,0,0,0.2)', borderRadius: '4px' }}>{error}</span>}
          <span style={{ fontSize: '11px', opacity: 0.6 }}>CPU: {cpuUsage.toFixed(1)}%</span>
        </div>
      </header>

      <main style={{ flex: 1, display: 'flex', gap: '20px', padding: '20px', overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div style={{
            flex: 1, position: 'relative', borderRadius: '12px', overflow: 'hidden',
            background: 'rgba(0,0,0,0.6)', border: '1px solid rgba(0,255,255,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '400px'
          }}>
            {isCameraActive ? (
              <video
                ref={videoRef}
                autoPlay muted playsInline
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <div style={{ textAlign: 'center', opacity: 0.5 }}>
                <div style={{ fontSize: '48px', marginBottom: '12px' }}>📷</div>
                <div style={{ fontSize: '14px' }}>Camera Off</div>
                <div style={{ fontSize: '11px', marginTop: '8px', color: '#888' }}>Click "Start Camera" to begin</div>
              </div>
            )}

            {latestResult && isCameraActive && (
              <div style={{
                position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, pointerEvents: 'none'
              }}>
                {latestResult.faces?.map((face: any, i: number) => (
                  <div key={`face-${i}`} style={{
                    position: 'absolute',
                    left: `${face.x || face.box?.x || 0}%`,
                    top: `${face.y || face.box?.y || 0}%`,
                    width: `${face.width || face.box?.width || 10}%`,
                    height: `${face.height || face.box?.height || 10}%`,
                    border: '2px solid #00ff88',
                    borderRadius: '8px',
                    boxShadow: '0 0 20px rgba(0,255,136,0.3), inset 0 0 20px rgba(0,255,136,0.1)'
                  }}>
                    <span style={{
                      position: 'absolute', top: '-20px', left: '0',
                      fontSize: '9px', color: '#00ff88', background: 'rgba(0,0,0,0.7)',
                      padding: '2px 6px', borderRadius: '3px', whiteSpace: 'nowrap'
                    }}>FACE {(face.confidence * 100).toFixed(0)}%</span>
                  </div>
                ))}
                {latestResult.hands?.map((hand: any, i: number) => (
                  <div key={`hand-${i}`} style={{
                    position: 'absolute',
                    left: `${hand.x || hand.box?.x || 0}%`,
                    top: `${hand.y || hand.box?.y || 0}%`,
                    width: `${hand.width || hand.box?.width || 8}%`,
                    height: `${hand.height || hand.box?.height || 8}%`,
                    border: '2px solid #ff00ff',
                    borderRadius: '4px',
                    boxShadow: '0 0 15px rgba(255,0,255,0.3)'
                  }}>
                    <span style={{
                      position: 'absolute', top: '-18px', left: '0',
                      fontSize: '9px', color: '#ff00ff', background: 'rgba(0,0,0,0.7)',
                      padding: '2px 6px', borderRadius: '3px', whiteSpace: 'nowrap'
                    }}>HAND {hand.type || i}</span>
                  </div>
                ))}
                {latestResult.objects?.map((obj: any, i: number) => (
                  <div key={`obj-${i}`} style={{
                    position: 'absolute',
                    left: `${obj.x || obj.box?.x || 0}%`,
                    top: `${obj.y || obj.box?.y || 0}%`,
                    width: `${obj.width || obj.box?.width || 10}%`,
                    height: `${obj.height || obj.box?.height || 10}%`,
                    border: '2px solid #ffff00',
                    borderRadius: '4px',
                    boxShadow: '0 0 15px rgba(255,255,0,0.3)'
                  }}>
                    <span style={{
                      position: 'absolute', top: '-18px', left: '0',
                      fontSize: '9px', color: '#ffff00', background: 'rgba(0,0,0,0.7)',
                      padding: '2px 6px', borderRadius: '3px', whiteSpace: 'nowrap'
                    }}>{obj.label || obj.class || 'OBJECT'} {(obj.confidence * 100).toFixed(0)}%</span>
                  </div>
                ))}
                {latestResult.pose && (
                  <div style={{
                    position: 'absolute',
                    left: `${latestResult.pose.x || latestResult.pose.box?.x || 0}%`,
                    top: `${latestResult.pose.y || latestResult.pose.box?.y || 0}%`,
                    width: `${latestResult.pose.width || latestResult.pose.box?.width || 15}%`,
                    height: `${latestResult.pose.height || latestResult.pose.box?.height || 30}%`,
                    border: '2px solid #ff6b00',
                    borderRadius: '8px',
                    boxShadow: '0 0 15px rgba(255,107,0,0.3)'
                  }}>
                    <span style={{
                      position: 'absolute', top: '-18px', left: '0',
                      fontSize: '9px', color: '#ff6b00', background: 'rgba(0,0,0,0.7)',
                      padding: '2px 6px', borderRadius: '3px'
                    }}>POSE</span>
                  </div>
                )}
              </div>
            )}

            {isProcessing && (
              <div style={{
                position: 'absolute', top: '15px', right: '15px',
                padding: '6px 12px', background: 'rgba(255,107,0,0.2)',
                border: '1px solid rgba(255,107,0,0.5)', borderRadius: '6px',
                fontSize: '10px', color: '#ff6b00', fontWeight: '600',
                textTransform: 'uppercase', letterSpacing: '1px'
              }}>Processing...</div>
            )}

            <div style={{
              position: 'absolute', bottom: '15px', left: '15px', right: '15px',
              display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center'
            }}>
              {modes.map(mode => (
                <button key={mode.key}
                  onClick={() => setMode(mode.key)}
                  style={{
                    padding: '6px 14px', borderRadius: '6px', border: `1px solid ${mode.color}`,
                    background: currentMode === mode.key ? `${mode.color}30` : 'rgba(0,0,0,0.5)',
                    color: currentMode === mode.key ? mode.color : '#888',
                    fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: '600',
                    cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '1px',
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = `${mode.color}20`; e.currentTarget.style.color = mode.color }}
                  onMouseLeave={e => { e.currentTarget.style.background = currentMode === mode.key ? `${mode.color}30` : 'rgba(0,0,0,0.5)'; e.currentTarget.style.color = currentMode === mode.key ? mode.color : '#888' }}
                >{mode.label}</button>
              ))}
            </div>
          </div>

          <div style={{
            padding: '15px', borderRadius: '8px',
            background: 'rgba(5,5,15,0.8)', border: '1px solid rgba(0,255,255,0.15)',
            display: 'flex', gap: '15px', alignItems: 'center', flexWrap: 'wrap'
          }}>
            <button
              onClick={handleToggleCamera}
              style={{
                padding: '10px 20px', borderRadius: '8px', border: 'none', cursor: 'pointer',
                fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', fontWeight: '600',
                textTransform: 'uppercase', letterSpacing: '1px',
                background: isCameraActive ? 'linear-gradient(135deg, #ff0000, #ff6b00)' : 'linear-gradient(135deg, #00ffff, #0088ff)',
                color: '#000', boxShadow: `0 0 20px ${isCameraActive ? 'rgba(255,0,0,0.4)' : 'rgba(0,255,255,0.4)'}`
              }}
            >{isCameraActive ? 'STOP CAMERA' : 'START CAMERA'}</button>

            {availableCameras.length > 1 && (
              <select
                value={cameraIndex}
                onChange={e => setCameraIndex(Number(e.target.value))}
                style={{
                  padding: '8px 14px', background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(0,255,255,0.3)',
                  borderRadius: '6px', color: '#e6e8f0', fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', cursor: 'pointer'
                }}
              >{availableCameras.map((cam, i) => (
                <option key={cam.deviceId} value={i}>{cam.label || `Camera ${i + 1}`}</option>
              ))}</select>
            )}

            <label style={{
              display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', cursor: 'pointer'
            }}>
              <input type="checkbox" checked={detectObjects} onChange={e => setDetectObjects(e.target.checked)}
                style={{ accentColor: '#00ffff' }} />
              Detect Objects
            </label>

            <div style={{ marginLeft: 'auto', fontSize: '10px', opacity: 0.5 }}>
              Detection: {(detectionConfidence * 100).toFixed(0)}% | Tracking: {(trackingConfidence * 100).toFixed(0)}%
            </div>
          </div>
        </div>

        <aside style={{
          width: '300px', display: 'flex', flexDirection: 'column', gap: '15px', overflow: 'auto', flexShrink: 0
        }}>
          <div style={{
            padding: '16px', borderRadius: '10px',
            background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(0,255,255,0.2)'
          }}>
            <h3 style={{ fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', color: '#00ffff', marginBottom: '12px' }}>
              DETECTION DATA
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '11px' }}>
              <Row label="Faces" value={latestResult?.faces?.length || 0} color="#00ff88" />
              <Row label="Hands" value={latestResult?.hands?.length || 0} color="#ff00ff" />
              <Row label="Objects" value={latestResult?.objects?.length || 0} color="#ffff00" />
              <Row label="Pose" value={latestResult?.pose ? 'Detected' : 'None'} color="#ff6b00" />
              <Row label="Timestamp" value={latestResult?.timestamp ? new Date(latestResult.timestamp).toLocaleTimeString() : '--'} color="#888" />
            </div>
          </div>

          <div style={{
            padding: '16px', borderRadius: '10px',
            background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(255,0,255,0.2)'
          }}>
            <h3 style={{ fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', color: '#ff00ff', marginBottom: '12px' }}>
              CONFIDENCE
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <ConfidenceBar label="Detection" value={detectionConfidence} color="#00ffff" />
              <ConfidenceBar label="Tracking" value={trackingConfidence} color="#ff00ff" />
            </div>
          </div>

          <div style={{
            padding: '16px', borderRadius: '10px',
            background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(255,107,0,0.2)'
          }}>
            <h3 style={{ fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', color: '#ff6b00', marginBottom: '12px' }}>
              STATUS
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '11px' }}>
              <Row label="Camera" value={isCameraActive ? 'Active' : 'Off'} color={isCameraActive ? '#00ff00' : '#888'} />
              <Row label="Processing" value={isProcessing ? 'Active' : 'Idle'} color={isProcessing ? '#ff6b00' : '#888'} />
              <Row label="FPS" value={fps} color={fps > 20 ? '#00ff00' : '#ff6b00'} />
              <Row label="Mode" value={currentMode} color="#00ffff" />
            </div>
          </div>
        </aside>
      </main>

      <style>{`
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.7; } }
        ::-webkit-scrollbar { width:6px; }
        ::-webkit-scrollbar-track { background:#050510; }
        ::-webkit-scrollbar-thumb { background:linear-gradient(180deg,#00ffff,#ff00ff); border-radius:3px; }
      `}</style>
    </div>
  )
}

const Row: React.FC<{ label: string; value: string | number; color: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
    <span style={{ opacity: 0.6 }}>{label}</span>
    <span style={{ color, fontWeight: '600' }}>{value}</span>
  </div>
)

const ConfidenceBar: React.FC<{ label: string; value: number; color: string }> = ({ label, value, color }) => (
  <div>
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', marginBottom: '4px', opacity: 0.7 }}>
      <span>{label}</span>
      <span>{(value * 100).toFixed(0)}%</span>
    </div>
    <div style={{ height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
      <div style={{ width: `${value * 100}%`, height: '100%', background: color, borderRadius: '2px', transition: 'width 0.3s', boxShadow: `0 0 8px ${color}` }} />
    </div>
  </div>
)

export default VisionDemo
