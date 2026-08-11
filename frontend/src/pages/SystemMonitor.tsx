import React, { useState, useEffect } from 'react'
import { useSystemStore } from '../store/useSystemStore'

export const SystemMonitor: React.FC = () => {
  const {
    os, cpu, memory, disk, network, gpu, battery,
    cpuHistory, memoryHistory, networkHistory, processes,
    stopMonitoring, startMonitoring
  } = useSystemStore()
  const [activeTab, setActiveTab] = useState<'overview' | 'processes' | 'gpu' | 'network'>('overview')
  const [sortBy, setSortBy] = useState<'cpu' | 'memory' | 'name'>('cpu')
  const [showMonitoring, setShowMonitoring] = useState(true)

  useEffect(() => {
    return () => stopMonitoring()
  }, [])

  const sortedProcesses = [...processes].sort((a, b) => {
    if (sortBy === 'cpu') return b.cpu - a.cpu
    if (sortBy === 'memory') return b.memory - a.memory
    return a.name.localeCompare(b.name)
  }).slice(0, 30)

  const tabs: { key: typeof activeTab; label: string; color: string }[] = [
    { key: 'overview', label: 'Overview', color: '#00ffff' },
    { key: 'processes', label: 'Processes', color: '#ff6b00' },
    { key: 'gpu', label: 'GPU', color: '#ff00ff' },
    { key: 'network', label: 'Network', color: '#00ff00' },
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
        borderBottom: '1px solid rgba(0,255,255,0.2)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <h1 style={{
            fontSize: '24px', fontWeight: '700', letterSpacing: '4px',
            background: 'linear-gradient(135deg, #00ffff, #ff6b00, #ff00ff)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text'
          }}>SYSTEM MONITOR</h1>
          <div style={{ display: 'flex', gap: '14px', fontSize: '11px', opacity: 0.7 }}>
            <span>OS: <strong style={{ color: '#00ffff' }}>{os}</strong></span>
            <span>|</span>
            <span>Cores: <strong style={{ color: '#ff6b00' }}>{cpu.cores}</strong></span>
            <span>|</span>
            <span>Freq: <strong style={{ color: '#00ff88' }}>{(cpu.frequency / 1000).toFixed(1)} GHz</strong></span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button onClick={() => { if (showMonitoring) stopMonitoring(); else startMonitoring(); setShowMonitoring(!showMonitoring) }}
            style={{
              padding: '6px 14px', borderRadius: '6px', border: `1px solid ${showMonitoring ? '#00ff00' : '#888'}`,
              background: showMonitoring ? 'rgba(0,255,0,0.15)' : 'transparent',
              color: showMonitoring ? '#00ff00' : '#888', fontFamily: "'JetBrains Mono', monospace",
              fontSize: '10px', cursor: 'pointer', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '1px'
            }}
          >{showMonitoring ? '● LIVE' : 'PAUSED'}</button>
        </div>
      </header>

      <div style={{ display: 'flex', gap: '12px', padding: '15px 30px', background: 'rgba(0,0,0,0.3)' }}>
        {tabs.map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '8px 18px', borderRadius: '8px',
              border: `1px solid ${activeTab === tab.key ? tab.color : 'rgba(255,255,255,0.1)'}`,
              background: activeTab === tab.key ? `${tab.color}20` : 'transparent',
              color: activeTab === tab.key ? tab.color : '#888',
              fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', fontWeight: '600',
              cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '1px'
            }}
          >{tab.label}</button>
        ))}
      </div>

      <main style={{ flex: 1, overflow: 'auto', padding: '20px 30px' }}>
        {activeTab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              <GaugeCard title="CPU" value={cpu.usage} color="#ff6b00" history={cpuHistory} subtitle={`${cpu.cores} cores • ${(cpu.frequency / 1000).toFixed(1)} GHz • ${cpu.temperature.toFixed(0)}°C`} />
              <GaugeCard title="MEMORY" value={memory.percentage} color="#00ffff" history={memoryHistory} subtitle={`${(memory.used / 1073741824).toFixed(1)} / ${(memory.total / 1073741824).toFixed(1)} GB`} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              <div style={{ padding: '20px', borderRadius: '12px', background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(0,255,136,0.2)' }}>
                <h3 style={{ fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', color: '#00ff88', marginBottom: '12px' }}>DISK</h3>
                <div style={{ marginBottom: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '6px' }}>
                    <span>{disk.percentage.toFixed(1)}% Used</span>
                    <span style={{ opacity: 0.6 }}>{(disk.used / 1073741824).toFixed(0)} / {(disk.total / 1073741824).toFixed(0)} GB</span>
                  </div>
                  <div style={{ height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ width: `${disk.percentage}%`, height: '100%', background: 'linear-gradient(90deg, #00ff88, #00cc66)', borderRadius: '3px', transition: 'width 0.5s' }} />
                  </div>
                </div>
                <div style={{ fontSize: '10px', opacity: 0.5 }}>Free: {(disk.free / 1073741824).toFixed(0)} GB</div>
              </div>
              <div style={{ padding: '20px', borderRadius: '12px', background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(255,107,0,0.2)' }}>
                <h3 style={{ fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', color: '#ff6b00', marginBottom: '12px' }}>SYSTEM INFO</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '11px' }}>
                  <Row label="OS" value={os} color="#00ffff" />
                  <Row label="CPU Temp" value={`${cpu.temperature.toFixed(0)}°C`} color={cpu.temperature > 70 ? '#ff0000' : cpu.temperature > 50 ? '#ff6b00' : '#00ff00'} />
                  <Row label="Battery" value={battery ? `${(battery.level * 100).toFixed(0)}% ${battery.charging ? '⚡' : ''}` : 'N/A'} color={battery ? (battery.level > 0.2 ? '#00ff00' : '#ff0000') : '#888'} />
                  <Row label="Processes" value={processes.length} color="#ff00ff" />
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'processes' && (
          <div style={{ borderRadius: '12px', background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(255,107,0,0.2)', overflow: 'hidden' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,107,0,0.15)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: '12px', fontSize: '10px' }}>
                <span style={{ opacity: 0.6 }}>Sort:</span>
                {(['cpu', 'memory', 'name'] as const).map(field => (
                  <button key={field} onClick={() => setSortBy(field)}
                    style={{
                      padding: '3px 10px', borderRadius: '4px', border: 'none',
                      background: sortBy === field ? 'rgba(255,107,0,0.3)' : 'transparent',
                      color: sortBy === field ? '#ff6b00' : '#888', cursor: 'pointer',
                      fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: '600',
                      textTransform: 'uppercase'
                    }}
                  >{field}</button>
                ))}
              </div>
              <div style={{ fontSize: '10px', opacity: 0.5 }}>{processes.length} processes</div>
            </div>
            <div style={{ overflow: 'auto', maxHeight: 'calc(100vh - 300px)' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,107,0,0.15)', color: '#888', fontSize: '9px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                    <th style={{ padding: '10px 20px', textAlign: 'left', fontWeight: '500' }}>PID</th>
                    <th style={{ padding: '10px 20px', textAlign: 'left', fontWeight: '500' }}>Name</th>
                    <th style={{ padding: '10px 20px', textAlign: 'right', fontWeight: '500' }}>CPU %</th>
                    <th style={{ padding: '10px 20px', textAlign: 'right', fontWeight: '500' }}>Memory MB</th>
                    <th style={{ padding: '10px 20px', textAlign: 'center', fontWeight: '500' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedProcesses.map((proc, i) => (
                    <tr key={proc.pid} style={{
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                      background: i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent'
                    }}>
                      <td style={{ padding: '8px 20px', color: '#888' }}>{proc.pid}</td>
                      <td style={{ padding: '8px 20px', fontWeight: '500' }}>{proc.name}</td>
                      <td style={{ padding: '8px 20px', textAlign: 'right', color: proc.cpu > 50 ? '#ff0000' : proc.cpu > 20 ? '#ff6b00' : '#00ff00' }}>
                        {proc.cpu.toFixed(1)}
                      </td>
                      <td style={{ padding: '8px 20px', textAlign: 'right', color: proc.memory > 300 ? '#ff6b00' : '#e6e8f0' }}>
                        {proc.memory.toFixed(0)}
                      </td>
                      <td style={{ padding: '8px 20px', textAlign: 'center' }}>
                        <span style={{
                          padding: '2px 8px', borderRadius: '3px', fontSize: '9px',
                          background: proc.status === 'running' ? 'rgba(0,255,0,0.15)' : 'rgba(255,255,255,0.05)',
                          color: proc.status === 'running' ? '#00ff00' : '#888',
                          textTransform: 'uppercase'
                        }}>{proc.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'gpu' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {gpu.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px', opacity: 0.4, background: 'rgba(5,5,15,0.9)', borderRadius: '12px', border: '1px solid rgba(255,0,255,0.2)' }}>
                <div style={{ fontSize: '48px', marginBottom: '12px' }}>🎮</div>
                <div>No GPU detected</div>
              </div>
            ) : gpu.map((g, i) => (
              <div key={i} style={{ padding: '24px', borderRadius: '12px', background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(255,0,255,0.2)', boxShadow: '0 0 30px rgba(255,0,255,0.05)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: '700', color: '#ff00ff', textShadow: '0 0 10px rgba(255,0,255,0.5)' }}>{g.name}</h3>
                  <span style={{ fontSize: '11px', opacity: 0.5 }}>#{i}</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  <GaugeCard title="GPU Usage" value={g.usage} color="#ff00ff" history={[]} subtitle="" compact />
                  <div style={{ padding: '16px', borderRadius: '8px', background: 'rgba(0,0,0,0.5)' }}>
                    <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.6, marginBottom: '8px' }}>Memory</div>
                    <div style={{ fontSize: '28px', fontWeight: '700', color: '#ff00ff', textShadow: '0 0 15px rgba(255,0,255,0.4)' }}>
                      {(g.memory.used / 1024).toFixed(1)} <span style={{ fontSize: '14px', opacity: 0.5 }}>/ {(g.memory.total / 1024).toFixed(1)} GB</span>
                    </div>
                    <div style={{ height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', marginTop: '10px', overflow: 'hidden' }}>
                      <div style={{ width: `${(g.memory.used / g.memory.total) * 100}%`, height: '100%', background: 'linear-gradient(90deg, #ff00ff, #ff0088)', borderRadius: '2px', transition: 'width 0.5s' }} />
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: '16px', fontSize: '11px', opacity: 0.6 }}>
                  Temperature: <span style={{ color: g.temperature > 80 ? '#ff0000' : '#ff6b00', fontWeight: '600' }}>{g.temperature.toFixed(0)}°C</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'network' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div style={{ padding: '24px', borderRadius: '12px', background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(0,255,0,0.2)', textAlign: 'center' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '2px', opacity: 0.6, marginBottom: '8px' }}>Download</div>
              <div style={{ fontSize: '36px', fontWeight: '700', color: '#00ff00', textShadow: '0 0 20px rgba(0,255,0,0.5)' }}>
                {network.download.toFixed(1)}
              </div>
              <div style={{ fontSize: '12px', opacity: 0.5 }}>MB/s</div>
              {networkHistory.length > 1 && (
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '60px', marginTop: '16px', justifyContent: 'center' }}>
                  {networkHistory.slice(-60).map((point, i) => (
                    <div key={i} style={{
                      width: '4px', height: `${Math.max(2, (point.download / Math.max(...networkHistory.map(p => p.download), 1)) * 60)}px`,
                      background: '#00ff00', borderRadius: '2px', opacity: 0.6
                    }} />
                  ))}
                </div>
              )}
            </div>
            <div style={{ padding: '24px', borderRadius: '12px', background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(0,255,255,0.2)', textAlign: 'center' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '2px', opacity: 0.6, marginBottom: '8px' }}>Upload</div>
              <div style={{ fontSize: '36px', fontWeight: '700', color: '#00ffff', textShadow: '0 0 20px rgba(0,255,255,0.5)' }}>
                {network.upload.toFixed(1)}
              </div>
              <div style={{ fontSize: '12px', opacity: 0.5 }}>MB/s</div>
              {networkHistory.length > 1 && (
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '60px', marginTop: '16px', justifyContent: 'center' }}>
                  {networkHistory.slice(-60).map((point, i) => (
                    <div key={i} style={{
                      width: '4px', height: `${Math.max(2, (point.upload / Math.max(...networkHistory.map(p => p.upload), 1)) * 60)}px`,
                      background: '#00ffff', borderRadius: '2px', opacity: 0.6
                    }} />
                  ))}
                </div>
              )}
            </div>
            <div style={{ gridColumn: '1 / -1', padding: '16px', borderRadius: '12px', background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(255,255,255,0.1)' }}>
              <h3 style={{ fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', opacity: 0.6, marginBottom: '10px' }}>Interfaces</h3>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                {network.interfaces.map((iface, i) => (
                  <span key={i} style={{ padding: '6px 12px', background: 'rgba(0,255,255,0.1)', border: '1px solid rgba(0,255,255,0.2)', borderRadius: '6px', fontSize: '11px', color: '#00ffff' }}>{iface}</span>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      <style>{`
        @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.7; } }
        ::-webkit-scrollbar { width:6px; }
        ::-webkit-scrollbar-track { background:#050510; }
        ::-webkit-scrollbar-thumb { background:linear-gradient(180deg,#00ffff,#ff6b00); border-radius:3px; }
      `}</style>
    </div>
  )
}

const GaugeCard: React.FC<{
  title: string; value: number; color: string;
  history?: number[]; subtitle?: string; compact?: boolean
}> = ({ title, value, color, history = [], subtitle = '', compact = false }) => {
  const r = 60
  const circumference = Math.PI * r
  const offset = circumference - (value / 100) * circumference

  return (
    <div style={{
      padding: '20px', borderRadius: '12px',
      background: 'rgba(5,5,15,0.9)', border: `1px solid ${color}30`,
      boxShadow: `0 0 30px ${color}10`
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: compact ? '10px' : '15px' }}>
        <h3 style={{ fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', color }}>{title}</h3>
        {!compact && subtitle && <span style={{ fontSize: '9px', opacity: 0.5 }}>{subtitle}</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <svg width="140" height="90" viewBox="0 0 140 90" style={{ flexShrink: 0 }}>
          <path d="M 20 80 A 60 60 0 0 1 120 80" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" strokeLinecap="round" />
          <path d="M 20 80 A 60 60 0 0 1 120 80" fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
            strokeDasharray={`${circumference}`} strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.5s ease', filter: `drop-shadow(0 0 6px ${color})` }} />
          <text x="70" y="55" textAnchor="middle" fill={color} fontSize="28" fontWeight="700" fontFamily="'JetBrains Mono', monospace">
            {value.toFixed(1)}%
          </text>
        </svg>
        {history.length > 1 && !compact && (
          <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: '2px', height: '60px' }}>
            {history.slice(-40).map((point, i) => (
              <div key={i} style={{
                width: '4px', height: `${Math.max(2, (point / 100) * 60)}px`,
                background: color, borderRadius: '2px', opacity: 0.4 + (point / 100) * 0.4,
                transition: 'height 0.3s'
              }} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

const Row: React.FC<{ label: string; value: string | number; color: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
    <span style={{ opacity: 0.6 }}>{label}</span>
    <span style={{ color, fontWeight: '600' }}>{value}</span>
  </div>
)

export default SystemMonitor
