import { create } from 'zustand'

interface VoiceState {
  isListening: boolean
  isSpeaking: boolean
  isProcessing: boolean
  wakeWordDetected: boolean
  transcript: string
  confidence: number
  error: string | null
  audioContext: AudioContext | null
  mediaStream: MediaStream | null
  analyser: AnalyserNode | null
  audioData: Uint8Array
  wakeWord: string
  wakeWordSensitivity: number
  sttEngine: 'whisper' | 'web' | 'cloud'
  ttsEngine: 'edge' | 'xtts' | 'elevenlabs'
  ttsVoice: string
  ttsRate: number
  ttsPitch: number
  ttsVolume: number
  conversationHistory: Array<{ role: 'user' | 'assistant'; content: string; timestamp: number; confidence?: number }>

  initialize: () => Promise<void>
  startListening: () => Promise<void>
  stopListening: () => void
  toggleListening: () => Promise<void>
  speak: (text: string, voice?: string) => Promise<void>
  stopSpeaking: () => void
  setTranscript: (text: string, confidence: number) => void
  addToHistory: (role: 'user' | 'assistant', content: string) => void
  clearHistory: () => void
  setWakeWord: (word: string) => void
  setWakeWordSensitivity: (sensitivity: number) => void
  setTtsEngine: (engine: 'edge' | 'xtts' | 'elevenlabs') => void
  setTtsVoice: (voice: string) => void
  setTtsSettings: (rate: number, pitch: number, volume: number) => void
  setError: (error: string | null) => void
  updateAudioData: (data: Uint8Array) => void
}

export const useVoiceStore = create<VoiceState>((set, get) => ({
    isListening: false,
    isSpeaking: false,
    isProcessing: false,
    wakeWordDetected: false,
    transcript: '',
    confidence: 0,
    error: null,
    audioContext: null,
    mediaStream: null,
    analyser: null,
    audioData: new Uint8Array(1024),
    wakeWord: 'jarvis',
    wakeWordSensitivity: 0.5,
    sttEngine: 'whisper',
    ttsEngine: 'edge',
    ttsVoice: 'en-US-JennyNeural',
    ttsRate: 1,
    ttsPitch: 1,
    ttsVolume: 1,
    conversationHistory: [],

    initialize: async () => {
      try {
        const AC = window.AudioContext || (window as any).webkitAudioContext
        const audioContext = new AC({ sampleRate: 16000 })
        set({ audioContext })
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
        })
        const analyser = audioContext.createAnalyser()
        analyser.fftSize = 2048
        analyser.smoothingTimeConstant = 0.8
        const source = audioContext.createMediaStreamSource(stream)
        source.connect(analyser)
        set({ mediaStream: stream, analyser, audioData: new Uint8Array(analyser.frequencyBinCount) })
      } catch (error) {
        console.error('Voice init failed:', error)
        set({ error: 'Microphone access denied' })
      }
    },

    startListening: async () => {
      const { isListening, analyser } = get()
      if (isListening || !analyser) return
      set({ isListening: true, error: null, wakeWordDetected: false })
      const processAudio = () => {
        const { isListening: il, analyser: an } = get()
        if (!il || !an) return
        const data = new Uint8Array(an.frequencyBinCount)
        an.getByteFrequencyData(data)
        set({ audioData: data })
        if (get().isListening) requestAnimationFrame(processAudio)
      }
      requestAnimationFrame(processAudio)
    },

    stopListening: () => set({ isListening: false, wakeWordDetected: false }),

    toggleListening: async () => {
      const { isListening } = get()
      isListening ? get().stopListening() : await get().startListening()
    },

    speak: async (text: string) => {
      if (get().isSpeaking) return
      set({ isSpeaking: true })
      try {
        const utterance = new SpeechSynthesisUtterance(text)
        utterance.rate = 1
        utterance.pitch = 1
        utterance.volume = 1
        speechSynthesis.speak(utterance)
        await new Promise(resolve => { utterance.onend = resolve })
      } finally {
        set({ isSpeaking: false })
      }
    },

    stopSpeaking: () => { speechSynthesis.cancel(); set({ isSpeaking: false }) },

    setTranscript: (text: string, confidence: number) => set({ transcript: text, confidence }),

    addToHistory: (role, content) => set(state => ({
      conversationHistory: [...state.conversationHistory, { role, content, timestamp: Date.now() }].slice(-50)
    })),

    clearHistory: () => set({ conversationHistory: [] }),
    setWakeWord: (word: string) => set({ wakeWord: word.toLowerCase() }),
    setWakeWordSensitivity: (sensitivity: number) => set({
      wakeWordSensitivity: Math.max(0, Math.min(1, sensitivity))
    }),
    setTtsEngine: (engine) => set({ ttsEngine: engine }),
    setTtsVoice: (voice: string) => set({ ttsVoice: voice }),
    setTtsSettings: (rate, pitch, volume) => set({ ttsRate: rate, ttsPitch: pitch, ttsVolume: volume }),
    setError: (error) => set({ error }),
    updateAudioData: (data) => set({ audioData: data })
}))

export default useVoiceStore
