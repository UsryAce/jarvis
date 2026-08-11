import { Canvas, useFrame } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import { useRef } from 'react'
import * as THREE from 'three'
import { useVisionStore } from '../../store/useVisionStore'
import { VoiceInterface } from '../VoiceInterface/VoiceInterface'
import { VisionOverlay } from '../Vision/VisionOverlay'

function ArcCore() {
  const core = useRef<THREE.Mesh>(null)
  const ring = useRef<THREE.Mesh>(null)
  useFrame(({ clock }, delta) => {
    if (core.current) {
      core.current.rotation.y += delta * 0.45
      const scale = 1 + Math.sin(clock.elapsedTime * 2) * 0.04
      core.current.scale.setScalar(scale)
    }
    if (ring.current) ring.current.rotation.z -= delta * 0.2
  })

  return (
    <group>
      <mesh ref={core}>
        <icosahedronGeometry args={[1.05, 2]} />
        <meshStandardMaterial color="#00dfff" emissive="#006d91" emissiveIntensity={1.8} wireframe />
      </mesh>
      <mesh ref={ring} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.55, 0.025, 10, 128]} />
        <meshBasicMaterial color="#00ffff" transparent opacity={0.8} />
      </mesh>
      <Html center position={[0, -1.9, 0]}>
        <div style={{ color: '#00ffff', whiteSpace: 'nowrap', letterSpacing: 4, fontSize: 12 }}>
          JARVIS HOLOGRAPHIC CORE
        </div>
      </Html>
    </group>
  )
}

const HolographicHUD = () => {
  const isCameraActive = useVisionStore(state => state.isCameraActive)

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: '#01070b' }}>
      <Canvas camera={{ position: [0, 0, 5], fov: 50 }}>
        <ambientLight intensity={0.35} />
        <pointLight position={[2, 3, 4]} color="#00ffff" intensity={8} />
        <ArcCore />
        <VoiceInterface position={[0, -2.35, 0]} scale={0.48} />
        {isCameraActive && <VisionOverlay />}
      </Canvas>
    </div>
  )
}

export default HolographicHUD
