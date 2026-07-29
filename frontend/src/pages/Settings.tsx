import React, { useState } from 'react'
import { useVoiceStore } from '../store/useVoiceStore'
import { useVisionStore } from '../store/useVisionStore'
import { useSystemStore } from '../store/useSystemStore'
import { useHomeStore } from '../store/useHomeStore'

export const Settings: React.FC = () => {
  const voice = useVoiceStore()
  const vision = useVisionStore()
  const system = useSystemStore()
  const home = useHomeStore()
  const [activeTab, setActiveTab] = useState<'voice' | 'vision' | 'system' | 'about'>('voice')

  const tabs: { key: typeof activeTab; label: string; color: string; icon: string }[] = [
    { key: 'voice', label: 'Voice', color: '#00ffff', icon: '🎤' },
    { key: 'vision', label: 'Vision', color: '#ff00ff', icon: '📷' },
    { key: 'system', label: 'System', color: '#ff6b00', icon: '⚙️' },
    { key: 'about', label: 'About', color: '#00ff88', icon: 'ℹ️' },
  ]

  const inputStyle: React.CSSProperties = {
    padding: '8px 12px', background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(0,255,255,0.3)',
    borderRadius: '6px', color: '#e6e8f0', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px',
    outline: 'none', width: '100%', boxSizing: 'border-box'
  }

  const selectStyle: React.CSSProperties = {
    ...inputStyle, cursor: 'pointer'
  }

  return (
    <div style={{
      width: '100%', height: '100%', display: 'flex', flexDirection: 'column',
      background: 'linear-gradient(135deg, #050510 0%, #0a0a1a 100%)',
      fontFamily: "'JetBrains Mono', monospace", color: '#e6e8f0', overflow: 'hidden'
    }}>
      <header style={{
        padding: '15px 30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'rgba(5,5,15,0.95)', backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(0,255,255,0.2)'
      }}>
        <h1 style={{
          fontSize: '24px', fontWeight: '700', letterSpacing: '4px',
          background: 'linear-gradient(135deg, #00ffff, #ff00ff, #ff6b00)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text'
        }}>SETTINGS</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px', opacity: 0.6 }}>
          <span>CPU: {system.cpuUsage.toFixed(1)}%</span>
          <span>|</span>
          <span>JARVIS v1.0.0</span>
        </div>
      </header>

      <div style={{ display: 'flex', gap: '8px', padding: '15px 30px', background: 'rgba(0,0,0,0.3)' }}>
        {tabs.map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '10px 20px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px',
              border: `1px solid ${activeTab === tab.key ? tab.color : 'rgba(255,255,255,0.1)'}`,
              background: activeTab === tab.key ? `${tab.color}20` : 'transparent',
              color: activeTab === tab.key ? tab.color : '#888',
              fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', fontWeight: '600',
              cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '1px', transition: 'all 0.2s'
            }}
          >{tab.icon} {tab.label}</button>
        ))}
      </div>

      <main style={{ flex: 1, overflow: 'auto', padding: '20px 30px' }}>
        {activeTab === 'voice' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '700px' }}>
            <Section title="Speech-to-Text" color="#00ffff">
              <Field label="Engine" color="#00ffff">
                <select value={voice.sttEngine} onChange={e => voice.setTtsEngine && voice.setTtsEngine(e.target.value as any)}
                  style={selectStyle}>
                  <option value="whisper">Whisper (Local)</option>
                  <option value="web">Web Speech API</option>
                  <option value="cloud">Cloud STT</option>
                </select>
              </Field>
            </Section>

            <Section title="Text-to-Speech" color="#ff00ff">
              <Field label="Engine" color="#ff00ff">
                <select value={voice.ttsEngine} onChange={e => voice.setTtsEngine && voice.setTtsEngine(e.target.value as any)}
                  style={selectStyle}>
                  <option value="edge">Edge TTS</option>
                  <option value="xtts">XTTS-v2</option>
                  <option value="elevenlabs">ElevenLabs</option>
                </select>
              </Field>
              <Field label="Voice" color="#ff00ff">
                <select value={voice.ttsVoice} onChange={e => voice.setTtsVoice && voice.setTtsVoice(e.target.value)}
                  style={selectStyle}>
                  <option value="en-US-JennyNeural">Jenny (US Female)</option>
                  <option value="en-US-GuyNeural">Guy (US Male)</option>
                  <option value="en-GB-SoniaNeural">Sonia (UK Female)</option>
                  <option value="en-GB-RyanNeural">Ryan (UK Male)</option>
                </select>
              </Field>
              <Field label="Rate" color="#ff00ff">
                <input type="range" min={0.5} max={2} step={0.1} value={voice.ttsRate}
                  onChange={e => voice.setTtsSettings && voice.setTtsSettings(Number(e.target.value), voice.ttsPitch, voice.ttsVolume)}
                  style={{ width: '100%', accentColor: '#ff00ff', cursor: 'pointer' }} />
                <span style={{ fontSize: '10px', opacity: 0.6, marginTop: '2px' }}>{voice.ttsRate.toFixed(1)}x</span>
              </Field>
            </Section>

            <Section title="Wake Word" color="#ff6b00">
              <Field label="Wake Word" color="#ff6b00">
                <input
                  value={voice.wakeWord}
                  onChange={e => voice.setWakeWord && voice.setWakeWord(e.target.value)}
                  placeholder="jarvis"
                  style={inputStyle} />
              </Field>
              <Field label="Sensitivity" color="#ff6b00">
                <input type="range" min={0} max={1} step={0.05} value={voice.wakeWordSensitivity}
                  onChange={e => voice.setWakeWordSensitivity && voice.setWakeWordSensitivity(Number(e.target.value))}
                  style={{ width: '100%', accentColor: '#ff6b00', cursor: 'pointer' }} />
                <span style={{ fontSize: '10px', opacity: 0.6, marginTop: '2px' }}>{(voice.wakeWordSensitivity * 100).toFixed(0)}%</span>
              </Field>
            </Section>

            <Section title="Status" color="#00ff88">
              <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', fontSize: '11px' }}>
                <StatusDot label="Microphone" active={!!voice.mediaStream} />
                <StatusDot label="Speaking" active={voice.isSpeaking} />
                <StatusDot label="Listening" active={voice.isListening} />
                <StatusDot label="Processing" active={voice.isProcessing} />
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'vision' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '700px' }}>
            <Section title="Camera" color="#ff00ff">
              <Field label="Default Camera" color="#ff00ff">
                <select value={vision.cameraIndex} onChange={e => vision.setCameraIndex(Number(e.target.value))}
                  style={selectStyle}>
                  <option value={0}>Camera 1</option>
                  <option value={1}>Camera 2</option>
                  <option value={2}>Camera 3</option>
                </select>
              </Field>
              <Field label="Detection Mode" color="#ff00ff">
                <select value={vision.currentMode} onChange={e => vision.setMode(e.target.value as typeof vision.currentMode)}
                  style={selectStyle}>
                  <option value="all">All</option>
                  <option value="face">Face Detection</option>
                  <option value="hands">Hand Tracking</option>
                  <option value="pose">Pose Estimation</option>
                  <option value="objects">Object Detection</option>
                </select>
              </Field>
            </Section>

            <Section title="Detection" color="#00ffff">
              <Field label="Detection Confidence" color="#00ffff">
                <input type="range" min={0} max={1} step={0.05} value={vision.detectionConfidence}
                  onChange={e => vision.setConfidence(Number(e.target.value), vision.trackingConfidence)}
                  style={{ width: '100%', accentColor: '#00ffff', cursor: 'pointer' }} />
                <span style={{ fontSize: '10px', opacity: 0.6, marginTop: '2px' }}>{(vision.detectionConfidence * 100).toFixed(0)}%</span>
              </Field>
              <Field label="Tracking Confidence" color="#00ffff">
                <input type="range" min={0} max={1} step={0.05} value={vision.trackingConfidence}
                  onChange={e => vision.setConfidence(vision.detectionConfidence, Number(e.target.value))}
                  style={{ width: '100%', accentColor: '#00ffff', cursor: 'pointer' }} />
                <span style={{ fontSize: '10px', opacity: 0.6, marginTop: '2px' }}>{(vision.trackingConfidence * 100).toFixed(0)}%</span>
              </Field>
            </Section>

            <Section title="Status" color="#ff6b00">
              <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', fontSize: '11px' }}>
                <StatusDot label="Camera" active={vision.isCameraActive} />
                <StatusDot label="Processing" active={vision.isProcessing} />
                <StatusDot label="Detection" active={!!vision.latestResult} />
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'system' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '700px' }}>
            <Section title="Monitoring" color="#ff6b00">
              <Field label="Update Interval" color="#ff6b00">
                <input type="range" min={500} max={10000} step={500} value={system.updateInterval}
                  onChange={e => system.setUpdateInterval(Number(e.target.value))}
                  style={{ width: '100%', accentColor: '#ff6b00', cursor: 'pointer' }} />
                <span style={{ fontSize: '10px', opacity: 0.6, marginTop: '2px' }}>{(system.updateInterval / 1000).toFixed(1)}s</span>
              </Field>
              <div style={{ display: 'flex', gap: '12px', marginTop: '10px' }}>
                <button onClick={() => system.startMonitoring()}
                  style={{ padding: '8px 16px', background: 'rgba(0,255,0,0.15)', border: '1px solid #00ff00', borderRadius: '6px', color: '#00ff00', fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', cursor: 'pointer', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  START MONITORING
                </button>
                <button onClick={() => system.stopMonitoring()}
                  style={{ padding: '8px 16px', background: 'rgba(255,0,0,0.15)', border: '1px solid #ff0000', borderRadius: '6px', color: '#ff0000', fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', cursor: 'pointer', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  STOP MONITORING
                </button>
              </div>
            </Section>

            <Section title="Home Integration" color="#00ffff">
              <Field label="MQTT Host" color="#00ffff">
                <input value={home.mqtt?.host || 'localhost'} readOnly
                  style={{ ...inputStyle, cursor: 'not-allowed', opacity: 0.6 }} />
              </Field>
              <Field label="Home Assistant" color="#00ffff">
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <input defaultValue={home.homeAssistant?.url || ''} placeholder="https://ha.example.com"
                    style={{ ...inputStyle, flex: 1 }} />
                  <input type="password" placeholder="Long-Lived Token"
                    style={{ ...inputStyle, flex: 1 }} />
                  <button
                    onClick={() => home.connectHomeAssistant && home.connectHomeAssistant(prompt('URL:') || '', prompt('Token:') || '')}
                    style={{ padding: '8px 14px', background: 'rgba(0,255,255,0.2)', border: '1px solid #00ffff', borderRadius: '6px', color: '#00ffff', fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', cursor: 'pointer', fontWeight: '600', whiteSpace: 'nowrap', textTransform: 'uppercase', letterSpacing: '1px' }}
                  >CONNECT</button>
                </div>
              </Field>
            </Section>

            <Section title="Appearance" color="#ff00ff">
              <Field label="Theme" color="#ff00ff">
                <div style={{ display: 'flex', gap: '12px' }}>
                  {['Dark', 'Light', 'Holographic'].map(t => (
                    <button key={t}
                      style={{
                        padding: '6px 14px', borderRadius: '6px', border: '1px solid rgba(255,0,255,0.3)',
                        background: t === 'Dark' ? 'rgba(255,0,255,0.2)' : 'rgba(255,255,255,0.05)',
                        color: t === 'Dark' ? '#ff00ff' : '#888', fontFamily: "'JetBrains Mono', monospace",
                        fontSize: '10px', cursor: 'pointer', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '1px'
                      }}
                    >{t}</button>
                  ))}
                </div>
              </Field>
              <Field label="Notifications" color="#ff00ff">
                <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '12px' }}>
                  <input type="checkbox" defaultChecked style={{ accentColor: '#ff00ff' }} />
                  Enable voice notifications
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '12px' }}>
                  <input type="checkbox" defaultChecked style={{ accentColor: '#ff00ff' }} />
                  Show system alerts
                </label>
              </Field>
            </Section>

            <Section title="Data" color="#ff6b00">
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button onClick={() => voice.clearHistory && voice.clearHistory()}
                  style={{ padding: '8px 14px', background: 'rgba(255,0,0,0.15)', border: '1px solid #ff0000', borderRadius: '6px', color: '#ff0000', fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', cursor: 'pointer', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  CLEAR HISTORY
                </button>
                <button
                  style={{ padding: '8px 14px', background: 'rgba(0,255,255,0.1)', border: '1px solid #00ffff', borderRadius: '6px', color: '#00ffff', fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', cursor: 'pointer', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  EXPORT DATA
                </button>
                <button
                  style={{ padding: '8px 14px', background: 'rgba(255,107,0,0.1)', border: '1px solid #ff6b00', borderRadius: '6px', color: '#ff6b00', fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', cursor: 'pointer', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  FACTORY RESET
                </button>
              </div>
            </Section>
          </div>
        )}

        {activeTab === 'about' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '600px' }}>
            <div style={{
              textAlign: 'center', padding: '40px', borderRadius: '16px',
              background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(0,255,255,0.2)',
              boxShadow: '0 0 60px rgba(0,255,255,0.05)'
            }}>
              <div style={{
                fontSize: '64px', fontWeight: '700', letterSpacing: '12px', marginBottom: '8px',
                background: 'linear-gradient(135deg, #00ffff, #ff00ff, #ff6b00)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text'
              }}>JARVIS</div>
              <div style={{ fontSize: '13px', opacity: 0.6, letterSpacing: '4px', textTransform: 'uppercase' }}>
                Just A Rather Very Intelligent System
              </div>
              <div style={{ marginTop: '20px', fontSize: '12px', opacity: 0.5 }}>
                Version 1.0.0
              </div>
            </div>

            <Section title="Model Information" color="#00ffff">
              <InfoRow label="Voice Model" value="Edge TTS + Whisper + Web Speech" />
              <InfoRow label="Vision Model" value="MediaPipe + YOLOv8 (simulated)" />
              <InfoRow label="LLM Backend" value="Nemotron 3 Ultra / GLM-5.2 / Kimi K2.6" />
              <InfoRow label="Embeddings" value="GPU-accelerated, real-time" />
            </Section>

            <Section title="System" color="#ff00ff">
              <InfoRow label="Platform" value={system.os || navigator.platform} />
              <InfoRow label="CPU Cores" value={`${system.cpu.cores}`} />
              <InfoRow label="Total RAM" value={`${(system.memory.total / 1073741824).toFixed(0)} GB`} />
              <InfoRow label="GPU" value={system.gpu[0]?.name || 'N/A'} />
            </Section>

            <Section title="Stack" color="#ff6b00">
              <InfoRow label="Frontend" value="React + Three.js + TypeScript" />
              <InfoRow label="State" value="Zustand + Immer" />
              <InfoRow label="3D Engine" value="Three.js + React Three Fiber" />
              <InfoRow label="Audio" value="Web Audio API" />
              <InfoRow label="Vision" value="MediaPipe + WebRTC (simulated)" />
            </Section>

            <Section title="Links" color="#00ff88">
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                {['GitHub', 'Documentation', 'API Reference', 'Discord', 'Twitter'].map(link => (
                  <a key={link} href="#" style={{
                    padding: '8px 16px', borderRadius: '6px',
                    background: 'rgba(0,255,136,0.1)', border: '1px solid rgba(0,255,136,0.2)',
                    color: '#00ff88', textDecoration: 'none', fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '1px',
                    transition: 'all 0.2s'
                  }} onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0,255,136,0.2)'; e.currentTarget.style.boxShadow = '0 0 20px rgba(0,255,136,0.2)' }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'rgba(0,255,136,0.1)'; e.currentTarget.style.boxShadow = 'none' }}
                  >{link}</a>
                ))}
              </div>
            </Section>
          </div>
        )}
      </main>

      <style>{`
        ::-webkit-scrollbar { width:6px; }
        ::-webkit-scrollbar-track { background:#050510; }
        ::-webkit-scrollbar-thumb { background:linear-gradient(180deg,#00ffff,#ff00ff); border-radius:3px; }
        input[type=range] { -webkit-appearance:none; height:4px; background:rgba(255,255,255,0.1); border-radius:2px; outline:none; }
        input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:14px; height:14px; border-radius:50%; cursor:pointer; }
        select { -webkit-appearance:none; background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6' fill='%23888'/%3E%3C/svg%3E"); background-repeat:no-repeat; background-position:right 12px center; padding-right:30px; }
        input:focus, select:focus { border-color:#00ffff !important; box-shadow:0 0 10px rgba(0,255,255,0.2); }
      `}</style>
    </div>
  )
}

const Section: React.FC<{ title: string; color: string; children: React.ReactNode }> = ({ title, color, children }) => (
  <div style={{ padding: '20px', borderRadius: '12px', background: 'rgba(5,5,15,0.9)', border: `1px solid ${color}25`, boxShadow: `0 0 20px ${color}08` }}>
    <h3 style={{ fontSize: '11px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', color, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color, boxShadow: `0 0 10px ${color}` }} />
      {title}
    </h3>
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>{children}</div>
  </div>
)

const Field: React.FC<{ label: string; color: string; children: React.ReactNode }> = ({ label, color, children }) => (
  <div>
    <div style={{ fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '1px', color, marginBottom: '6px' }}>{label}</div>
    {children}
  </div>
)

const StatusDot: React.FC<{ label: string; active: boolean }> = ({ label, active }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
    <span style={{
      width: '8px', height: '8px', borderRadius: '50%',
      background: active ? '#00ff00' : '#666',
      boxShadow: active ? '0 0 10px #00ff00' : 'none'
    }} />
    <span style={{ opacity: active ? 1 : 0.5 }}>{label}</span>
  </div>
)

const InfoRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
    <span style={{ fontSize: '11px', opacity: 0.6 }}>{label}</span>
    <span style={{ fontSize: '11px', color: '#e6e8f0', textAlign: 'right' }}>{value}</span>
  </div>
)

export default Settings
