import { create } from 'zustand'

export interface DeviceState {
  entity_id: string
  device_type: 'light' | 'switch' | 'climate' | 'cover' | 'lock' | 'media_player' | 'sensor' | 'camera' | 'vacuum' | 'fan'
  name: string
  state: string
  attributes: Record<string, any>
  last_updated: Date
  available: boolean
}

export interface Scene {
  name: string
  entities: Record<string, Record<string, any>>
  icon: string
}

interface HomeState {
  mqtt: {
    connected: boolean
    host: string
    port: number
  }
  homeAssistant: {
    connected: boolean
    url: string
  }
  devices: Record<string, DeviceState>
  scenes: Record<string, Scene>
  currentScene: string | null

  initialize: () => Promise<void>
  connectMQTT: () => Promise<void>
  disconnectMQTT: () => void
  connectHomeAssistant: (url: string, token: string) => Promise<void>
  disconnectHomeAssistant: () => void
  turnOn: (entity_id: string, options?: Record<string, any>) => Promise<void>
  turnOff: (entity_id: string) => Promise<void>
  setBrightness: (entity_id: string, brightness: number) => Promise<void>
  setColor: (entity_id: string, rgb: [number, number, number]) => Promise<void>
  setTemperature: (entity_id: string, temperature: number) => Promise<void>
  setCoverPosition: (entity_id: string, position: number) => Promise<void>
  lock: (entity_id: string) => Promise<void>
  unlock: (entity_id: string) => Promise<void>
  playMedia: (entity_id: string, media_content_id: string, media_content_type: string) => Promise<void>
  mediaPlay: (entity_id: string) => Promise<void>
  mediaPause: (entity_id: string) => Promise<void>
  mediaStop: (entity_id: string) => Promise<void>
  setVolume: (entity_id: string, volume: number) => Promise<void>
  activateScene: (scene_name: string) => Promise<void>
  goodMorning: () => Promise<void>
  goodNight: () => Promise<void>
  movieTime: () => Promise<void>
  partyMode: () => Promise<void>
  awayMode: () => Promise<void>
  allLightsOn: (brightness?: number) => Promise<void>
  allLightsOff: () => Promise<void>
  lockAllDoors: () => Promise<void>
  setThermostat: (temperature: number) => Promise<void>
  getDashboardData: () => any
}

export const useHomeStore = create<HomeState>()(
  (set, get) => ({
    mqtt: {
      connected: false,
      host: 'localhost',
      port: 1883
    },
    homeAssistant: {
      connected: false,
      url: ''
    },
    devices: {},
    scenes: {},
    currentScene: null,

    initialize: async () => {
      // Initialize MQTT
      try {
        await get().connectMQTT()
      } catch (e) {
        console.warn('MQTT connection failed:', e)
      }

      // Initialize Home Assistant if configured
      const haUrl = localStorage.getItem('HA_URL')
      const haToken = localStorage.getItem('HA_TOKEN')
      if (haUrl && haToken) {
        await get().connectHomeAssistant(haUrl, haToken)
      }
    },

    connectMQTT: async () => {
      // MQTT connection logic
      set({ mqtt: { ...get().mqtt, connected: true } })
    },

    disconnectMQTT: () => {
      set({ mqtt: { ...get().mqtt, connected: false } })
    },

    connectHomeAssistant: async (url: string, token: string) => {
      // Home Assistant connection logic
      localStorage.setItem('HA_URL', url)
      localStorage.setItem('HA_TOKEN', token)
      set({ homeAssistant: { ...get().homeAssistant, connected: true, url } })
    },

    disconnectHomeAssistant: () => {
      set({ homeAssistant: { ...get().homeAssistant, connected: false, url: '' } })
    },

    // Device control methods
    turnOn: async (entity_id: string, options: Record<string, any> = {}) => {
      // Implementation would call MQTT or HA API
      console.log('Turn on:', entity_id, options)
    },

    turnOff: async (entity_id: string) => {
      console.log('Turn off:', entity_id)
    },

    setBrightness: async (entity_id: string, brightness: number) => {
      console.log('Set brightness:', entity_id, brightness)
    },

    setColor: async (entity_id: string, rgb: [number, number, number]) => {
      console.log('Set color:', entity_id, rgb)
    },

    setTemperature: async (entity_id: string, temperature: number) => {
      console.log('Set temperature:', entity_id, temperature)
    },

    setCoverPosition: async (entity_id: string, position: number) => {
      console.log('Set cover position:', entity_id, position)
    },

    lock: async (entity_id: string) => {
      console.log('Lock:', entity_id)
    },

    unlock: async (entity_id: string) => {
      console.log('Unlock:', entity_id)
    },

    playMedia: async (entity_id: string, media_content_id: string, media_content_type: string) => {
      console.log('Play media:', entity_id, media_content_id, media_content_type)
    },

    mediaPlay: async (entity_id: string) => {
      console.log('Media play:', entity_id)
    },

    mediaPause: async (entity_id: string) => {
      console.log('Media pause:', entity_id)
    },

    mediaStop: async (entity_id: string) => {
      console.log('Media stop:', entity_id)
    },

    setVolume: async (entity_id: string, volume: number) => {
      console.log('Set volume:', entity_id, volume)
    },

    activateScene: async (scene_name: string) => {
      const { scenes } = get()
      const scene = scenes[scene_name]
      if (!scene) return

      for (const [entity_id, state_data] of Object.entries(scene.entities)) {
        const state = state_data.state
        if (state === 'on') {
          await get().turnOn(entity_id, state_data)
        } else if (state === 'off') {
          await get().turnOff(entity_id)
        } else if (state === 'locked') {
          await get().lock(entity_id)
        } else if (state === 'unlocked') {
          await get().unlock(entity_id)
        } else if (state_data.brightness !== undefined) {
          await get().setBrightness(entity_id, state_data.brightness)
        } else if (state_data.temperature !== undefined) {
          await get().setTemperature(entity_id, state_data.temperature)
        } else if (state_data.position !== undefined) {
          await get().setCoverPosition(entity_id, state_data.position)
        }
      }
      set({ currentScene: scene_name })
    },

    // Scene shortcuts
    goodMorning: () => get().activateScene('good_morning'),
    goodNight: () => get().activateScene('good_night'),
    movieTime: () => get().activateScene('movie_time'),
    partyMode: () => get().activateScene('party_mode'),
    awayMode: () => get().activateScene('away_mode'),

    allLightsOn: async (brightness = 100) => {
      const lights = Object.entries(get().devices).filter(([_, d]) => d.device_type === 'light')
      for (const [entity_id] of lights) {
        await get().turnOn(entity_id, { brightness })
      }
    },

    allLightsOff: async () => {
      const lights = Object.entries(get().devices).filter(([_, d]) => d.device_type === 'light')
      for (const [entity_id] of lights) {
        await get().turnOff(entity_id)
      }
    },

    lockAllDoors: async () => {
      const locks = Object.entries(get().devices).filter(([_, d]) => d.device_type === 'lock')
      for (const [entity_id] of locks) {
        await get().lock(entity_id)
      }
    },

    setThermostat: async (temperature: number) => {
      const thermostats = Object.entries(get().devices).filter(([_, d]) => d.device_type === 'climate')
      for (const [entity_id] of thermostats) {
        await get().setTemperature(entity_id, temperature)
      }
    },

    getDashboardData: () => {
      const { devices } = get()
      return {
        lights: Object.values(devices).filter(d => d.device_type === 'light'),
        switches: Object.values(devices).filter(d => d.device_type === 'switch'),
        climate: Object.values(devices).filter(d => d.device_type === 'climate'),
        covers: Object.values(devices).filter(d => d.device_type === 'cover'),
        locks: Object.values(devices).filter(d => d.device_type === 'lock'),
        sensors: Object.values(devices).filter(d => d.device_type === 'sensor'),
        media_players: Object.values(devices).filter(d => d.device_type === 'media_player'),
        scenes: Object.values(get().scenes).map(s => ({ name: s.name, icon: s.icon })),
        total_devices: Object.keys(devices).length,
        online_devices: Object.values(devices).filter(d => d.available).length
      }
    }
  }))

export default useHomeStore
