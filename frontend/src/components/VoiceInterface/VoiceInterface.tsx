import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useVoiceStore } from '../../store/useVoiceStore'
import './VoiceSwarm.css'

export type VoiceAgentMode = 'cowork' | 'council' | 'swarm'

export interface VoiceAgentSummary {
  id: string
  name: string
  role?: string
  status: 'idle' | 'working' | 'blocked' | 'complete'
}

interface VoiceInterfaceProps {
  position?: [number, number, number]
  scale?: number
  mode?: VoiceAgentMode
  onModeChange?: (mode: VoiceAgentMode) => void
  maxAgents?: number
  onMaxAgentsChange?: (count: number) => void
  activeAgents?: number
  activeTasks?: number
  missionStatus?: string
  agents?: VoiceAgentSummary[]
  swarmAvailable?: boolean
  handsFree?: boolean
  onHandsFreeChange?: (enabled: boolean) => void
  onPushToTalkStart?: () => void
  onPushToTalkEnd?: () => void
}

const MODES: Array<{ id: VoiceAgentMode; label: string; description: string }> = [
  { id: 'cowork', label: 'COWORK', description: 'Specialists divide one mission' },
  { id: 'council', label: 'COUNCIL', description: 'Agents debate, judge verifies' },
  { id: 'swarm', label: 'SWARM', description: 'Parallel projects and task graph' },
]

const clampAgentCount = (count: number) => Math.min(8, Math.max(2, Math.round(count)))

const statusLabel = (
  isListening: boolean,
  isSpeaking: boolean,
  isProcessing: boolean,
  wakeWordDetected: boolean,
) => {
  if (wakeWordDetected) return 'WAKE WORD DETECTED'
  if (isListening) return 'LISTENING'
  if (isSpeaking) return 'JARVIS SPEAKING'
  if (isProcessing) return 'PROCESSING MISSION'
  return 'VOICE LINK READY'
}

export const VoiceInterface: React.FC<VoiceInterfaceProps> = ({
  position = [0, -2, -2],
  scale = 1,
  mode: controlledMode,
  onModeChange,
  maxAgents: controlledMaxAgents,
  onMaxAgentsChange,
  activeAgents = 0,
  activeTasks = 0,
  missionStatus = 'Awaiting your mission',
  agents = [],
  swarmAvailable = false,
  handsFree: controlledHandsFree,
  onHandsFreeChange,
  onPushToTalkStart,
  onPushToTalkEnd,
}) => {
  const {
    isListening,
    isSpeaking,
    isProcessing,
    wakeWordDetected,
    transcript,
    confidence,
    error,
    initialize,
    startListening,
    stopListening,
    stopSpeaking,
  } = useVoiceStore()

  const [localMode, setLocalMode] = useState<VoiceAgentMode>(() => {
    const stored = localStorage.getItem('jarvis_voice_agent_mode')
    return stored === 'council' || stored === 'swarm' ? stored : 'cowork'
  })
  const [localMaxAgents, setLocalMaxAgents] = useState(() =>
    clampAgentCount(Number(localStorage.getItem('jarvis_voice_max_agents')) || 4),
  )
  const [localHandsFree, setLocalHandsFree] = useState(
    () => localStorage.getItem('jarvis_voice_hands_free') === 'true',
  )
  const [isPushing, setIsPushing] = useState(false)

  const mode = controlledMode ?? localMode
  const maxAgents = clampAgentCount(controlledMaxAgents ?? localMaxAgents)
  const handsFree = controlledHandsFree ?? localHandsFree
  const ringRef = useRef<THREE.Mesh>(null)
  const particlesRef = useRef<THREE.Points>(null)
  const coreMaterialRef = useRef<THREE.ShaderMaterial>(null)
  const waveformGeometry = useMemo(() => {
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(128 * 3), 3))
    return geometry
  }, [])
  const particlePositions = useMemo(
    () => Float32Array.from({ length: 500 * 3 }, () => (Math.random() - 0.5) * 2),
    [],
  )
  const waveformLine = useMemo(() => {
    const material = new THREE.LineBasicMaterial({
      color: '#00eaff',
      transparent: true,
      opacity: 0.88,
      blending: THREE.AdditiveBlending,
    })
    return new THREE.Line(waveformGeometry, material)
  }, [waveformGeometry])

  useEffect(() => () => {
    waveformGeometry.dispose()
    ;(waveformLine.material as THREE.Material).dispose()
  }, [waveformGeometry, waveformLine])

  useFrame(({ clock }) => {
    const elapsed = clock.getElapsedTime()
    const voice = useVoiceStore.getState()
    const source = voice.audioData
    const positions = waveformGeometry.attributes.position.array as Float32Array
    for (let index = 0; index < 128; index += 1) {
      const sourceIndex = Math.floor((index * source.length) / 128)
      const activity = voice.isListening || voice.isSpeaking ? source[sourceIndex] / 255 : 0
      positions[index * 3] = (index / 127) * 2 - 1
      positions[index * 3 + 1] = activity * 0.5
      positions[index * 3 + 2] = 0
    }
    waveformGeometry.attributes.position.needsUpdate = true

    if (ringRef.current) {
      const pulse = Math.sin(elapsed * 3) * 0.1 + 1
      ringRef.current.scale.setScalar(pulse)
      ;(ringRef.current.material as THREE.MeshBasicMaterial).opacity = 0.3 + Math.sin(elapsed * 4) * 0.12
      ringRef.current.rotation.z += 0.005
    }
    if (particlesRef.current) {
      particlesRef.current.rotation.y += 0.001
      particlesRef.current.rotation.x += 0.0005
    }
    if (coreMaterialRef.current) {
      coreMaterialRef.current.uniforms.time.value = elapsed
      coreMaterialRef.current.uniforms.isListening.value = voice.isListening
      coreMaterialRef.current.uniforms.isSpeaking.value = voice.isSpeaking
    }
  })

  const selectMode = useCallback((nextMode: VoiceAgentMode) => {
    setLocalMode(nextMode)
    localStorage.setItem('jarvis_voice_agent_mode', nextMode)
    onModeChange?.(nextMode)
  }, [onModeChange])

  const updateMaxAgents = useCallback((nextCount: number) => {
    const clamped = clampAgentCount(nextCount)
    setLocalMaxAgents(clamped)
    localStorage.setItem('jarvis_voice_max_agents', String(clamped))
    onMaxAgentsChange?.(clamped)
  }, [onMaxAgentsChange])

  const setHandsFree = useCallback(async (enabled: boolean) => {
    setLocalHandsFree(enabled)
    localStorage.setItem('jarvis_voice_hands_free', String(enabled))
    onHandsFreeChange?.(enabled)
    if (enabled) {
      if (!useVoiceStore.getState().analyser) await initialize()
      await startListening()
    } else if (!isPushing) {
      stopListening()
    }
  }, [initialize, isPushing, onHandsFreeChange, startListening, stopListening])

  const beginPushToTalk = useCallback(async () => {
    setIsPushing(true)
    if (isSpeaking) stopSpeaking()
    if (!useVoiceStore.getState().analyser) await initialize()
    await startListening()
    onPushToTalkStart?.()
  }, [initialize, isSpeaking, onPushToTalkStart, startListening, stopSpeaking])

  const endPushToTalk = useCallback(() => {
    setIsPushing(false)
    if (!handsFree) stopListening()
    onPushToTalkEnd?.()
  }, [handsFree, onPushToTalkEnd, stopListening])

  const displayedAgents = agents.slice(0, maxAgents)
  const voiceStatus = statusLabel(isListening, isSpeaking, isProcessing, wakeWordDetected)

  return (
    <group position={position} scale={scale}>
      <mesh ref={ringRef} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.2, 1.5, 64]} />
        <meshBasicMaterial color="#00eaff" transparent opacity={0.3} side={THREE.DoubleSide} blending={THREE.AdditiveBlending} />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.8, 1, 64]} />
        <meshBasicMaterial color="#7a5cff" transparent opacity={0.22} side={THREE.DoubleSide} blending={THREE.AdditiveBlending} />
      </mesh>

      <primitive object={waveformLine} position={[0, 0, 0.1]} />

      <mesh>
        <sphereGeometry args={[0.3, 32, 32]} />
        <shaderMaterial
          ref={coreMaterialRef}
          vertexShader={coreVertexShader}
          fragmentShader={coreFragmentShader}
          uniforms={{
            time: { value: 0 },
            isListening: { value: false },
            isSpeaking: { value: false },
          }}
          transparent
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      <points ref={particlesRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" array={particlePositions} itemSize={3} count={particlePositions.length / 3} />
        </bufferGeometry>
        <pointsMaterial size={0.02} color="#55ecff" transparent opacity={0.55} sizeAttenuation blending={THREE.AdditiveBlending} />
      </points>

      {[0, 1, 2].map((index) => (
        <mesh key={index} rotation={[-Math.PI / 2, 0, 0]} scale={1 + index * 0.5}>
          <ringGeometry args={[1.5, 1.6, 32]} />
          <meshBasicMaterial
            color={['#00eaff', '#7a5cff', '#ffb454'][index]}
            transparent
            opacity={0.13}
            side={THREE.DoubleSide}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
      ))}

      <Html position={[0, -1.52, 0]} center style={{ pointerEvents: 'none' }}>
        <div className={`voice-swarm-status ${isListening ? 'is-live' : ''}`} aria-live="polite">
          <span className="voice-swarm-status__pulse" />
          {voiceStatus}
        </div>
      </Html>

      <Html position={[2.25, 0.25, 0.2]} center wrapperClass="voice-swarm-html">
        <section className="voice-swarm-console" aria-label="Jarvis voice agent controls">
          <header className="voice-swarm-console__header">
            <div>
              <span className="voice-swarm-console__eyebrow">VOICE COMMAND // AGENT NETWORK</span>
              <h2>Mission Control</h2>
            </div>
            <span className={`voice-swarm-console__link ${swarmAvailable ? 'is-online' : ''}`}>
              {swarmAvailable ? 'NETWORK ONLINE' : 'LOCAL READY'}
            </span>
          </header>

          <div className="voice-swarm-modes" role="group" aria-label="Agent collaboration mode">
            {MODES.map((item) => (
              <button
                key={item.id}
                type="button"
                className={mode === item.id ? 'is-selected' : ''}
                aria-pressed={mode === item.id}
                title={item.description}
                onClick={() => selectMode(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="voice-swarm-metrics" aria-label="Agent activity">
            <div><strong>{activeAgents}</strong><span>ACTIVE AGENTS</span></div>
            <div><strong>{activeTasks}</strong><span>LIVE TASKS</span></div>
            <div><strong>{maxAgents}</strong><span>AGENT LIMIT</span></div>
          </div>

          <label className="voice-swarm-range">
            <span><b>Parallel capacity</b><output>{maxAgents} / 8</output></span>
            <input
              type="range"
              min="2"
              max="8"
              step="1"
              value={maxAgents}
              onChange={(event) => updateMaxAgents(Number(event.target.value))}
              aria-label="Maximum parallel agents"
            />
          </label>

          <div className="voice-swarm-mission" aria-live="polite">
            <span>SPOKEN MISSION STATUS</span>
            <p>{missionStatus}</p>
            {transcript ? (
              <small>“{transcript}” · {Math.round(confidence * 100)}% confidence</small>
            ) : (
              <small>Say “Jarvis” followed by a goal</small>
            )}
          </div>

          {displayedAgents.length > 0 ? (
            <ul className="voice-swarm-agents" aria-label="Active agent roster">
              {displayedAgents.map((agent) => (
                <li key={agent.id}>
                  <span className={`voice-swarm-agent-dot is-${agent.status}`} />
                  <b>{agent.name}</b>
                  <small>{agent.role ?? agent.status}</small>
                </li>
              ))}
            </ul>
          ) : null}

          {error ? <p className="voice-swarm-error" role="alert">{error}</p> : null}

          <div className="voice-swarm-talk-controls">
            <button
              type="button"
              className={`voice-swarm-handsfree ${handsFree ? 'is-enabled' : ''}`}
              aria-pressed={handsFree}
              onClick={() => void setHandsFree(!handsFree)}
            >
              <span>HANDS-FREE</span>
              <b>{handsFree ? 'ON' : 'OFF'}</b>
            </button>
            <button
              type="button"
              className={`voice-swarm-ptt ${isPushing ? 'is-active' : ''}`}
              onPointerDown={() => void beginPushToTalk()}
              onPointerUp={endPushToTalk}
              onPointerCancel={endPushToTalk}
              onPointerLeave={() => { if (isPushing) endPushToTalk() }}
              onKeyDown={(event) => {
                if ((event.key === ' ' || event.key === 'Enter') && !isPushing) void beginPushToTalk()
              }}
              onKeyUp={(event) => {
                if (event.key === ' ' || event.key === 'Enter') endPushToTalk()
              }}
            >
              <span className="voice-swarm-ptt__icon">◉</span>
              <span><b>{isPushing ? 'LISTENING' : 'PUSH TO TALK'}</b><small>Hold to issue a mission</small></span>
            </button>
          </div>
        </section>
      </Html>
    </group>
  )
}

const coreVertexShader = `
  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vWorldPosition;
  void main() {
    vUv = uv;
    vNormal = normalize(normalMatrix * normal);
    vWorldPosition = (modelMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const coreFragmentShader = `
  uniform float time;
  uniform bool isListening;
  uniform bool isSpeaking;
  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vWorldPosition;
  void main() {
    float basePulse = 1.0 + sin(time * 3.0) * 0.2;
    float listenPulse = isListening ? (sin(time * 10.0) * 0.15 + 0.15) : 0.0;
    float speakPulse = isSpeaking ? (sin(time * 15.0) * 0.25 + 0.25) : 0.0;
    vec3 color = mix(vec3(0.0, 0.92, 1.0), vec3(0.48, 0.36, 1.0), sin(time * 0.5) * 0.5 + 0.5);
    vec3 viewDir = normalize(cameraPosition - vWorldPosition);
    float fresnel = pow(1.0 - max(dot(normalize(vNormal), viewDir), 0.0), 2.0);
    float core = smoothstep(0.5, 0.0, length(vUv - 0.5));
    vec3 finalColor = color * (basePulse + listenPulse + speakPulse + fresnel * 0.5 + core * 0.3);
    float alpha = 0.3 + fresnel * 0.5 + core * 0.5;
    gl_FragColor = vec4(finalColor, alpha);
  }
`

export default VoiceInterface
