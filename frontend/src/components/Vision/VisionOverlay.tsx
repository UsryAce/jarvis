import { Html } from '@react-three/drei'
import { useVisionStore } from '../../store/useVisionStore'

interface VisionOverlayProps {
  position?: [number, number, number]
}

export const VisionOverlay = ({ position = [0, 1.5, -2] }: VisionOverlayProps) => {
  const result = useVisionStore(state => state.latestResult)
  const faceCount = result?.faces.length ?? 0
  const handCount = result?.hands.length ?? 0
  const objectCount = result?.objects.length ?? 0

  return (
    <group position={position}>
      <mesh>
        <planeGeometry args={[3.8, 0.75]} />
        <meshBasicMaterial color="#00151d" transparent opacity={0.82} />
      </mesh>
      <lineSegments>
        <edgesGeometry args={[undefined]} />
        <lineBasicMaterial color="#00ffff" />
      </lineSegments>
      <Html center transform position={[0, 0, 0.02]}>
        <div style={{ minWidth: 300, color: '#8ffcff', fontFamily: 'monospace', textAlign: 'center' }}>
          VISION · FACES {faceCount} · HANDS {handCount} · OBJECTS {objectCount}
        </div>
      </Html>
    </group>
  )
}

export default VisionOverlay
