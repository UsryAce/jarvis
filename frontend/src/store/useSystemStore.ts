import { create } from 'zustand'

interface SystemState {
  // System info
  os: string
  cpu: {
    usage: number
    cores: number
    frequency: number
    temperature: number
  }
  memory: {
    total: number
    used: number
    free: number
    percentage: number
  }
  disk: {
    total: number
    used: number
    free: number
    percentage: number
  }
  network: {
    upload: number
    download: number
    interfaces: string[]
  }
  // Flat compatibility values consumed by dashboard-style views.
  cpuUsage: number
  memoryUsage: number
  networkSpeed: { upload: number; download: number }
  processes: Array<{
    pid: number
    name: string
    cpu: number
    memory: number
    status: string
  }>

  // GPU info
  gpu: {
    name: string
    usage: number
    memory: { used: number; total: number }
    temperature: number
  }[]

  // Battery
  battery: {
    level: number
    charging: boolean
    timeRemaining: number
  } | null

  // Settings
  updateInterval: number
  historyLength: number

  // History
  cpuHistory: number[]
  memoryHistory: number[]
  networkHistory: { upload: number; download: number }[]
  monitoring: boolean
  monitorInterval: ReturnType<typeof setInterval> | null

  // Actions
  initialize: () => Promise<void>
  refresh: () => Promise<void>
  startMonitoring: () => void
  stopMonitoring: () => void
  setUpdateInterval: (interval: number) => void
  killProcess: (pid: number) => Promise<void>
  getProcessList: () => Promise<void>
}

interface BatteryManager {
  level: number
  charging: boolean
  dischargingTime: number
}

interface BatteryNavigator extends Navigator {
  getBattery?: () => Promise<BatteryManager>
}

export const useSystemStore = create<SystemState>()(
  (set, get) => ({
    // Initial state
    os: 'Unknown',
    cpu: { usage: 0, cores: 0, frequency: 0, temperature: 0 },
    memory: { total: 0, used: 0, free: 0, percentage: 0 },
    disk: { total: 0, used: 0, free: 0, percentage: 0 },
    network: { upload: 0, download: 0, interfaces: [] },
    cpuUsage: 0,
    memoryUsage: 0,
    networkSpeed: { upload: 0, download: 0 },
    processes: [],
    gpu: [],
    battery: null,
    updateInterval: 2000,
    historyLength: 60,
    cpuHistory: [],
    memoryHistory: [],
    networkHistory: [],

    // Monitoring state
    monitoring: false,
    monitorInterval: null as any,

    initialize: async () => {
      await get().refresh()
      get().startMonitoring()
    },

    refresh: async () => {
      try {
        // In a real implementation, this would call a system info API
        // For now, we'll simulate with mock data
        const mockData = {
          os: navigator.platform,
          cpu: {
            usage: Math.random() * 30 + 10,
            cores: navigator.hardwareConcurrency || 4,
            frequency: 3200,
            temperature: Math.random() * 20 + 40
          },
          memory: {
            total: 16 * 1024 * 1024 * 1024,
            used: (8 + Math.random() * 4) * 1024 * 1024 * 1024,
            free: 0,
            percentage: 0
          },
          disk: {
            total: 512 * 1024 * 1024 * 1024,
            used: (200 + Math.random() * 100) * 1024 * 1024 * 1024,
            free: 0,
            percentage: 0
          },
          network: {
            upload: Math.random() * 10,
            download: Math.random() * 50,
            interfaces: ['eth0', 'wlan0']
          },
          gpu: [
            {
              name: 'NVIDIA RTX 3080',
              usage: Math.random() * 50,
              memory: { used: 4000, total: 10240 },
              temperature: Math.random() * 20 + 45
            }
          ],
          battery: (navigator as BatteryNavigator).getBattery
            ? await (navigator as BatteryNavigator).getBattery!().then(value => ({
                level: value.level,
                charging: value.charging,
                timeRemaining: value.dischargingTime
              }))
            : null
        }

        // Calculate percentages
        mockData.memory.free = mockData.memory.total - mockData.memory.used
        mockData.memory.percentage = (mockData.memory.used / mockData.memory.total) * 100
        mockData.disk.free = mockData.disk.total - mockData.disk.used
        mockData.disk.percentage = (mockData.disk.used / mockData.disk.total) * 100

        // Mock processes
        const processes = Array.from({ length: 20 }, (_, i) => ({
          pid: 1000 + i,
          name: ['chrome', 'firefox', 'code', 'node', 'python', 'docker', 'postgres', 'redis'][i % 8] + (i > 7 ? ` ${i}` : ''),
          cpu: Math.random() * 20,
          memory: Math.random() * 500 + 50,
          status: ['running', 'sleeping', 'idle'][Math.floor(Math.random() * 3)]
        }))

        set(state => ({
          os: mockData.os,
          cpu: mockData.cpu,
          memory: mockData.memory,
          disk: mockData.disk,
          network: mockData.network,
          cpuUsage: mockData.cpu.usage,
          memoryUsage: mockData.memory.percentage,
          networkSpeed: {
            upload: mockData.network.upload,
            download: mockData.network.download
          },
          gpu: mockData.gpu,
          battery: mockData.battery,
          processes: processes,
          cpuHistory: [...state.cpuHistory.slice(-state.historyLength), mockData.cpu.usage],
          memoryHistory: [...state.memoryHistory.slice(-state.historyLength), mockData.memory.percentage],
          networkHistory: [...state.networkHistory.slice(-state.historyLength), { upload: mockData.network.upload, download: mockData.network.download }]
        }))
      } catch (error) {
        console.error('System refresh failed:', error)
      }
    },

    startMonitoring: () => {
      const { monitoring, updateInterval } = get()
      if (monitoring) return

      set({ monitoring: true })

      const interval = setInterval(() => {
        get().refresh()
      }, updateInterval)

      set({ monitorInterval: interval })
    },

    stopMonitoring: () => {
      const { monitorInterval } = get()
      if (monitorInterval) {
        clearInterval(monitorInterval)
      }
      set({ monitoring: false, monitorInterval: null })
    },

    setUpdateInterval: (interval: number) => {
      set({ updateInterval: Math.max(500, interval) })
      if (get().monitoring) {
        get().stopMonitoring()
        get().startMonitoring()
      }
    },

    killProcess: async (pid: number) => {
      console.log('Kill process:', pid)
      // Would call backend API to kill process
    },

    getProcessList: async () => {
      // Would fetch from backend
    }
  }))

export default useSystemStore
