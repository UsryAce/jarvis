import { create } from 'zustand'

export interface VisionFace {
  bbox: [number, number, number, number]
  confidence: number
  emotion?: string
  gaze?: string
}

export interface VisionHand {
  landmarks: Array<[number, number, number?]>
  handedness: 'Left' | 'Right' | string
  gestures?: string[]
}

interface VisionState {
  isCameraActive: boolean
  latestResult: {
    faces: VisionFace[]
    hands: VisionHand[]
    pose: any | null
    objects: any[]
    timestamp: number
  } | null
  cameraStream: MediaStream | null
  videoElement: HTMLVideoElement | null
  isProcessing: boolean
  error: string | null
  currentMode: 'face' | 'hands' | 'pose' | 'objects' | 'all'
  cameraIndex: number
  detectionConfidence: number
  trackingConfidence: number

  startCamera: (index?: number) => Promise<void>
  stopCamera: () => void
  setMode: (mode: 'face' | 'hands' | 'pose' | 'objects' | 'all') => void
  setCameraIndex: (index: number) => void
  setConfidence: (detection: number, tracking: number) => void
  updateResults: (results: any) => void
  setError: (error: string | null) => void
  setProcessing: (processing: boolean) => void
}

export const useVisionStore = create<VisionState>()(
  (set, get) => ({
    isCameraActive: false,
    latestResult: null,
    cameraStream: null,
    videoElement: null,
    isProcessing: false,
    error: null,
    currentMode: 'all',
    cameraIndex: 0,
    detectionConfidence: 0.5,
    trackingConfidence: 0.5,

    startCamera: async (index = 0) => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            deviceId: { exact: (await navigator.mediaDevices.enumerateDevices())
              .filter(d => d.kind === 'videoinput')[index]?.deviceId },
            width: { ideal: 1280 },
            height: { ideal: 720 },
            frameRate: { ideal: 30 }
          }
        })

        const video = document.createElement('video')
        video.srcObject = stream
        video.autoplay = true
        video.muted = true
        video.playsInline = true
        await video.play()

        set({
          cameraStream: stream,
          videoElement: video,
          isCameraActive: true,
          cameraIndex: index,
          error: null
        })

        // Start processing
        startProcessingLoop()
      } catch (error) {
        console.error('Camera start failed:', error)
        set({ error: 'Camera access denied or unavailable' })
      }
    },

    stopCamera: () => {
      const { cameraStream } = get()
      if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop())
      }
      set({
        cameraStream: null,
        isCameraActive: false,
        videoElement: null
      })
    },

    setMode: (mode: any) => {
      set({ currentMode: mode })
    },

    setCameraIndex: (index: number) => {
      set({ cameraIndex: index })
      if (get().isCameraActive) {
        get().stopCamera()
        get().startCamera(index)
      }
    },

    setConfidence: (detection: number, tracking: number) => {
      set({
        detectionConfidence: Math.max(0, Math.min(1, detection)),
        trackingConfidence: Math.max(0, Math.min(1, tracking))
      })
    },

    updateResults: (results: any) => {
      set({ latestResult: { ...results, timestamp: Date.now() } })
    },

    setError: (error: string | null) => {
      set({ error })
    },

    setProcessing: (processing: boolean) => {
      set({ isProcessing: processing })
    }
  })
)

function startProcessingLoop() {
  // Processing loop would be implemented with requestAnimationFrame
  // and MediaPipe or TensorFlow.js models
}

export default useVisionStore
