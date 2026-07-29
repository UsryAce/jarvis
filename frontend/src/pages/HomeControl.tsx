import React, { useState, useEffect } from 'react'
import { useHomeStore } from '../store/useHomeStore'
import { useSystemStore } from '../store/useSystemStore'

export const HomeControl: React.FC = () => {
  const {
    devices, scenes, currentScene, mqtt, homeAssistant,
    turnOn, turnOff, setBrightness,
    activateScene, goodMorning, goodNight, movieTime, partyMode, awayMode, lockAllDoors,
    setThermostat, getDashboardData
  } = useHomeStore()
  const { memoryUsage } = useSystemStore()
  const [activeTab, setActiveTab] = useState<'lights' | 'climate' | 'scenes' | 'devices'>('lights')
  const [thermostatTemp, setThermostatTemp] = useState(72)

  const dashboardData = getDashboardData()

  useEffect(() => {
    const climateDevices = Object.values(devices).filter(d => d.device_type === 'climate')
    if (climateDevices.length > 0 && climateDevices[0].attributes?.temperature) {
      setThermostatTemp(climateDevices[0].attributes.temperature)
    }
  }, [devices])

  const handleThermostatChange = async (delta: number) => {
    const newTemp = Math.max(60, Math.min(90, thermostatTemp + delta))
    setThermostatTemp(newTemp)
    await setThermostat(newTemp)
  }

  const quickActions = [
    { label: 'Good Morning', icon: '🌅', onClick: goodMorning, color: '#ff6b00' },
    { label: 'Good Night', icon: '🌙', onClick: goodNight, color: '#00ffff' },
    { label: 'Movie Time', icon: '🎬', onClick: movieTime, color: '#ff00ff' },
    { label: 'Party Mode', icon: '🎉', onClick: partyMode, color: '#ff00ff' },
    { label: 'Away Mode', icon: '🚪', onClick: awayMode, color: '#ff6b00' },
    { label: 'Lock All', icon: '🔒', onClick: lockAllDoors, color: '#ff0000' },
  ]

  const lights = Object.entries(devices).filter(([_, d]) => d.device_type === 'light')
  const climateDevices = Object.entries(devices).filter(([_, d]) => d.device_type === 'climate')
  const sensors = Object.entries(devices).filter(([_, d]) => d.device_type === 'sensor')

  const tabs: { key: typeof activeTab; label: string; color: string; count?: number }[] = [
    { key: 'lights', label: 'Lights', color: '#00ffff', count: lights.length },
    { key: 'climate', label: 'Climate', color: '#ff6b00', count: climateDevices.length },
    { key: 'scenes', label: 'Scenes', color: '#ff00ff', count: Object.keys(scenes).length },
    { key: 'devices', label: 'All Devices', color: '#00ff00', count: Object.keys(devices).length },
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
            background: 'linear-gradient(135deg, #00ffff, #ff6b00)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text'
          }}>HOME CONTROL</h1>
          <div style={{ display: 'flex', gap: '14px', fontSize: '11px', opacity: 0.7 }}>
            <span>MQTT: <span style={{ color: mqtt.connected ? '#00ff00' : '#ff0000' }}>{mqtt.connected ? 'CONNECTED' : 'OFFLINE'}</span></span>
            <span>|</span>
            <span>HA: <span style={{ color: homeAssistant.connected ? '#00ff00' : '#888' }}>{homeAssistant.connected ? 'LINKED' : 'NOT SETUP'}</span></span>
            <span>|</span>
            <span>Devices: <span style={{ color: '#00ffff' }}>{dashboardData.online_devices}/{dashboardData.total_devices} online</span></span>
          </div>
        </div>
        {currentScene && (
          <div style={{
            padding: '6px 14px', background: 'rgba(255,0,255,0.15)',
            border: '1px solid rgba(255,0,255,0.4)', borderRadius: '6px',
            fontSize: '10px', color: '#ff00ff', fontWeight: '600',
            textTransform: 'uppercase', letterSpacing: '1px'
          }}>Scene: {currentScene.replace(/_/g, ' ')}</div>
        )}
      </header>

      <div style={{ display: 'flex', gap: '12px', padding: '15px 30px', background: 'rgba(0,0,0,0.3)' }}>
        {tabs.map(tab => (
          <button key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '8px 18px', borderRadius: '8px',
              border: `1px solid ${activeTab === tab.key ? tab.color : 'rgba(255,255,255,0.1)'}`,
              background: activeTab === tab.key ? `${tab.color}20` : 'transparent',
              color: activeTab === tab.key ? tab.color : '#888',
              fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', fontWeight: '600',
              cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '1px',
              transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: '8px'
            }}
          >
            {tab.label}
            {tab.count !== undefined && <span style={{ fontSize: '9px', opacity: 0.6 }}>({tab.count})</span>}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: '10px', opacity: 0.4, display: 'flex', alignItems: 'center' }}>
          RAM: {memoryUsage.toFixed(1)}%
        </div>
      </div>

      <main style={{ flex: 1, display: 'flex', gap: '20px', padding: '20px 30px', overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '15px', overflow: 'auto' }}>
          {activeTab === 'lights' && (
            <>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={() => useHomeStore.getState().allLightsOn()}
                  style={{ padding: '8px 16px', background: 'rgba(0,255,255,0.2)', border: '1px solid #00ffff', borderRadius: '6px', color: '#00ffff', fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: '600', cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '1px' }}>ALL ON</button>
                <button onClick={() => useHomeStore.getState().allLightsOff()}
                  style={{ padding: '8px 16px', background: 'rgba(255,0,0,0.2)', border: '1px solid #ff0000', borderRadius: '6px', color: '#ff0000', fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: '600', cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '1px' }}>ALL OFF</button>
              </div>
              {lights.length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px', opacity: 0.4 }}>
                  <div style={{ fontSize: '36px', marginBottom: '12px' }}>💡</div>
                  <div>No lights configured</div>
                  <div style={{ fontSize: '11px', marginTop: '8px' }}>Connect Home Assistant or MQTT to add devices</div>
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px' }}>
                {lights.map(([id, device]) => (
                  <div key={id} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '14px 16px', borderRadius: '10px',
                    background: 'rgba(5,5,15,0.8)', border: `1px solid ${device.state === 'on' ? 'rgba(0,255,255,0.4)' : 'rgba(255,255,255,0.08)'}`,
                    boxShadow: device.state === 'on' ? '0 0 20px rgba(0,255,255,0.1)' : 'none'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{
                        width: '10px', height: '10px', borderRadius: '50%',
                        background: device.state === 'on' ? '#00ffff' : '#444',
                        boxShadow: device.state === 'on' ? '0 0 15px #00ffff' : 'none'
                      }} />
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: '500' }}>{device.name}</div>
                        <div style={{ fontSize: '9px', opacity: 0.5, marginTop: '2px' }}>
                          {device.state === 'on' ? `Brightness: ${device.attributes?.brightness || 100}%` : 'Off'}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      {device.state === 'on' && (
                        <input type="range" min={1} max={100} value={device.attributes?.brightness || 100}
                          onChange={e => setBrightness(id, Number(e.target.value))}
                          style={{ width: '80px', accentColor: '#00ffff', cursor: 'pointer' }} />
                      )}
                      <button onClick={() => device.state === 'on' ? turnOff(id) : turnOn(id)}
                        style={{
                          padding: '6px 14px', background: device.state === 'on' ? 'rgba(255,0,0,0.2)' : 'rgba(0,255,255,0.2)',
                          border: `1px solid ${device.state === 'on' ? '#ff0000' : '#00ffff'}`,
                          borderRadius: '5px', color: device.state === 'on' ? '#ff0000' : '#00ffff',
                          fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', fontWeight: '600', cursor: 'pointer',
                          textTransform: 'uppercase'
                        }}
                      >{device.state === 'on' ? 'OFF' : 'ON'}</button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {activeTab === 'climate' && (
            <>
              {climateDevices.length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px', opacity: 0.4 }}>
                  <div style={{ fontSize: '36px', marginBottom: '12px' }}>🌡️</div>
                  <div>No climate devices configured</div>
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '15px' }}>
                {climateDevices.map(([id, device]) => (
                  <div key={id} style={{
                    padding: '20px', borderRadius: '12px',
                    background: 'rgba(5,5,15,0.8)', border: '1px solid rgba(255,107,0,0.3)',
                    textAlign: 'center'
                  }}>
                    <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.6, marginBottom: '8px' }}>{device.name}</div>
                    <div style={{ fontSize: '42px', fontWeight: '700', color: '#ff6b00', textShadow: '0 0 20px rgba(255,107,0,0.5)' }}>
                      {device.attributes?.temperature || thermostatTemp}°
                    </div>
                    <div style={{ fontSize: '11px', opacity: 0.6, marginTop: '4px' }}>
                      Target: {device.attributes?.target_temp || thermostatTemp}° | Humidity: {device.attributes?.humidity || '--'}%
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', marginTop: '16px' }}>
                      <button onClick={() => handleThermostatChange(-1)}
                        style={{ width: '44px', height: '44px', borderRadius: '50%', background: 'rgba(0,255,255,0.15)', border: '1px solid rgba(0,255,255,0.4)', color: '#00ffff', fontSize: '20px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>−</button>
                      <button onClick={() => handleThermostatChange(1)}
                        style={{ width: '44px', height: '44px', borderRadius: '50%', background: 'rgba(255,0,0,0.15)', border: '1px solid rgba(255,0,0,0.4)', color: '#ff0000', fontSize: '20px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>+</button>
                    </div>
                    <div style={{ fontSize: '10px', opacity: 0.5, marginTop: '12px' }}>
                      {device.state === 'heat' ? 'Heating' : device.state === 'cool' ? 'Cooling' : device.state === 'off' ? 'Off' : device.state}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {activeTab === 'scenes' && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px' }}>
                {Object.entries(scenes).map(([key, scene]) => (
                  <button key={key} onClick={() => activateScene(key)}
                    style={{
                      padding: '20px', borderRadius: '12px',
                      background: currentScene === key ? 'rgba(255,0,255,0.2)' : 'rgba(5,5,15,0.8)',
                      border: `1px solid ${currentScene === key ? '#ff00ff' : 'rgba(255,0,255,0.2)'}`,
                      boxShadow: currentScene === key ? '0 0 30px rgba(255,0,255,0.2)' : 'none',
                      color: '#fff', cursor: 'pointer', fontFamily: "'JetBrains Mono', monospace",
                      textAlign: 'center', transition: 'all 0.2s'
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,0,255,0.15)'; e.currentTarget.style.borderColor = '#ff00ff' }}
                    onMouseLeave={e => { e.currentTarget.style.background = currentScene === key ? 'rgba(255,0,255,0.2)' : 'rgba(5,5,15,0.8)'; e.currentTarget.style.borderColor = currentScene === key ? '#ff00ff' : 'rgba(255,0,255,0.2)' }}
                  >
                    <div style={{ fontSize: '36px', marginBottom: '8px' }}>{scene.icon}</div>
                    <div style={{ fontSize: '12px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '1px' }}>{scene.name}</div>
                    {currentScene === key && <div style={{ fontSize: '9px', color: '#ff00ff', marginTop: '6px' }}>● ACTIVE</div>}
                  </button>
                ))}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: '10px' }}>
                {quickActions.map((action, i) => (
                  <button key={i} onClick={action.onClick}
                    style={{
                      padding: '14px', borderRadius: '10px',
                      background: `${action.color}15`, border: `1px solid ${action.color}40`,
                      color: action.color, cursor: 'pointer', fontFamily: "'JetBrains Mono', monospace",
                      textAlign: 'center', transition: 'all 0.2s', fontSize: '11px', fontWeight: '600',
                      textTransform: 'uppercase', letterSpacing: '1px'
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = `${action.color}30`; e.currentTarget.style.boxShadow = `0 0 20px ${action.color}30` }}
                    onMouseLeave={e => { e.currentTarget.style.background = `${action.color}15`; e.currentTarget.style.boxShadow = 'none' }}
                  >{action.icon} {action.label}</button>
                ))}
              </div>
            </>
          )}

          {activeTab === 'devices' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {Object.entries(devices).length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px', opacity: 0.4 }}>
                  <div style={{ fontSize: '36px', marginBottom: '12px' }}>📡</div>
                  <div>No devices found</div>
                </div>
              )}
              {Object.entries(devices).map(([id, device]) => (
                <div key={id} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '12px 16px', borderRadius: '8px',
                  background: 'rgba(5,5,15,0.6)', border: '1px solid rgba(255,255,255,0.08)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ color: device.available ? '#00ff00' : '#ff0000', fontSize: '8px' }}>●</span>
                    <DeviceIcon type={device.device_type} />
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: '500' }}>{device.name}</div>
                      <div style={{ fontSize: '9px', opacity: 0.5 }}>
                        {device.device_type} • {device.state}
                      </div>
                    </div>
                  </div>
                  <div style={{ fontSize: '9px', opacity: 0.4 }}>#{device.entity_id}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <aside style={{
          width: '260px', display: 'flex', flexDirection: 'column', gap: '15px', flexShrink: 0, overflow: 'auto'
        }}>
          <div style={{ padding: '16px', borderRadius: '10px', background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(0,255,255,0.2)' }}>
            <h3 style={{ fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', color: '#00ffff', marginBottom: '12px' }}>
              SYSTEM STATUS
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '11px' }}>
              <Row label="MQTT" value={mqtt.connected ? 'Connected' : 'Offline'} color={mqtt.connected ? '#00ff00' : '#ff0000'} />
              <Row label="Home Assistant" value={homeAssistant.connected ? 'Linked' : 'Not Set Up'} color={homeAssistant.connected ? '#00ff00' : '#888'} />
              <Row label="Active Scene" value={currentScene ? currentScene.replace(/_/g, ' ') : 'None'} color={currentScene ? '#ff00ff' : '#888'} />
              <Row label="Total Devices" value={dashboardData.total_devices} color="#00ffff" />
              <Row label="Online" value={dashboardData.online_devices} color="#00ff00" />
            </div>
          </div>
          <div style={{ padding: '16px', borderRadius: '10px', background: 'rgba(5,5,15,0.9)', border: '1px solid rgba(255,107,0,0.2)' }}>
            <h3 style={{ fontSize: '10px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '2px', color: '#ff6b00', marginBottom: '12px' }}>
              SENSORS
            </h3>
            {sensors.length === 0 ? (
              <div style={{ fontSize: '11px', opacity: 0.4, textAlign: 'center', padding: '10px' }}>No sensors</div>
            ) : sensors.map(([id, sensor]) => (
              <div key={id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <span style={{ opacity: 0.7 }}>{sensor.name}</span>
                <span style={{ color: '#ff6b00', fontWeight: '600' }}>{sensor.state}{sensor.attributes?.unit_of_measurement || ''}</span>
              </div>
            ))}
          </div>
        </aside>
      </main>

      <style>{`
        ::-webkit-scrollbar { width:6px; }
        ::-webkit-scrollbar-track { background:#050510; }
        ::-webkit-scrollbar-thumb { background:linear-gradient(180deg,#00ffff,#ff6b00); border-radius:3px; }
        input[type=range] { -webkit-appearance:none; height:4px; background:rgba(0,255,255,0.3); border-radius:2px; outline:none; }
        input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:14px; height:14px; border-radius:50%; background:#00ffff; cursor:pointer; box-shadow:0 0 10px #00ffff; }
      `}</style>
    </div>
  )
}

const DeviceIcon: React.FC<{ type: string }> = ({ type }) => {
  const icons: Record<string, string> = {
    light: '💡', switch: '🔌', climate: '🌡️', cover: '🪟',
    lock: '🔒', media_player: '📺', sensor: '📊', camera: '📷',
    vacuum: '🧹', fan: '🌀'
  }
  return <span style={{ fontSize: '16px' }}>{icons[type] || '📦'}</span>
}

const Row: React.FC<{ label: string; value: string | number; color: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
    <span style={{ opacity: 0.6 }}>{label}</span>
    <span style={{ color, fontWeight: '600' }}>{value}</span>
  </div>
)

export default HomeControl
