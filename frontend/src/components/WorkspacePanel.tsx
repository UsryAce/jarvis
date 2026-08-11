import { useEffect, useRef, useState } from 'react'
import {
  Bluetooth, BookmarkPlus, Check, Code2, ExternalLink, FileSearch, FileText, Globe2,
  Loader2, Play, PlugZap, RefreshCw, Save, Search, Send,
  Settings, Trash2, Unplug, Wrench,
} from 'lucide-react'
import { api } from '../services/api'

type Tone = 'good' | 'warn'
type Props = {
  label: string
  onCommand: (text: string) => void
  onToast: (text: string, tone?: Tone) => void
}
type Item = Record<string, any>

const workspaceCopy: Record<string, string> = {
  FILES: 'Search the JARVIS workspace, preview text files, and open a selected file with its Windows application.',
  NOTES: 'Capture persistent notes and manage the saved note archive.',
  BROWSER: 'Validate and open web destinations, with local bookmarks for frequent services.',
  CODE: 'Execute confirmed Python in an isolated temporary process with a ten-second limit.',
  TASKS: 'Create, prioritize, complete, and remove persistent tasks.',
  TOOLS: 'Search the installed NVIDIA skill catalog and hand a selected capability to Jarvis.',
  BLUETOOTH: 'Discover and connect nearby devices through the browser Web Bluetooth permission flow.',
  SETTINGS: 'Configure voice authority and interface preferences stored by the Jarvis backend.',
}

function WorkspacePanel({ label, onCommand, onToast }: Props) {
  const [value, setValue] = useState('')
  const [items, setItems] = useState<Item[]>([])
  const [output, setOutput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [priority, setPriority] = useState('medium')
  const [bookmarks, setBookmarks] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('jarvis_bookmarks') || '[]') }
    catch { return [] }
  })
  const [preferences, setPreferences] = useState({ auto_mic: true, clear_wake: true, owner_voice_only: true, sensitivity: 6, ui_preference: 'dashboard' })
  const bluetoothDevices = useRef<Map<string, any>>(new Map())

  const load = async () => {
    setBusy(true); setError('')
    try {
      if (label === 'NOTES') setItems((await api.listNotes()).notes || [])
      if (label === 'TASKS') setItems((await api.listTasks()).tasks || [])
      if (label === 'TOOLS') setItems((await api.getNvidiaSkills('', 30)).skills || [])
      if (label === 'SETTINGS') {
        const data = await api.getDashboardState()
        if (data.preferences && typeof data.preferences === 'object') setPreferences(current => ({ ...current, ...(data.preferences as Partial<typeof current>) }))
      }
      if (label === 'BLUETOOTH') {
        const manager = (navigator as any).bluetooth
        if (!manager) throw new Error('Web Bluetooth is not available in this browser')
        const devices = manager.getDevices ? await manager.getDevices() : []
        bluetoothDevices.current = new Map(devices.map((device: any) => [device.id, device]))
        setItems(devices.map((device: any) => ({ id: device.id, name: device.name || 'Unnamed device', connected: Boolean(device.gatt?.connected) })))
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : `${label} workspace could not load`)
    } finally { setBusy(false) }
  }

  useEffect(() => { void load() }, [label])

  const searchFiles = async () => {
    if (!value.trim()) return
    setBusy(true); setError(''); setOutput('')
    try { setItems((await api.searchFiles(value.trim())).results || []) }
    catch { setError('File search failed') }
    finally { setBusy(false) }
  }

  const previewFile = async (path: string) => {
    setBusy(true); setError('')
    try { setOutput((await api.readFile(path)).content || 'No preview available') }
    catch (previewError: any) { setError(previewError?.response?.data?.detail || 'File preview failed') }
    finally { setBusy(false) }
  }

  const saveNote = async () => {
    if (!value.trim()) return
    setBusy(true)
    try { await api.createNote(value.trim()); setValue(''); await load(); onToast('Note saved', 'good') }
    catch { setError('Note could not be saved') }
    finally { setBusy(false) }
  }

  const createTask = async () => {
    if (!value.trim()) return
    setBusy(true)
    try { await api.createTask(value.trim(), priority); setValue(''); await load(); onToast('Task created', 'good') }
    catch { setError('Task could not be created') }
    finally { setBusy(false) }
  }

  const openUrl = async (raw = value) => {
    const normalized = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`
    setError('')
    try {
      await api.openBrowser(normalized)
      const opened = window.open(normalized, '_blank', 'noopener,noreferrer')
      onToast(opened ? 'Browser opened' : 'Allow popups to open this URL', opened ? 'good' : 'warn')
    } catch { setError('Enter a valid HTTP(S) address') }
  }

  const addBookmark = () => {
    const normalized = /^https?:\/\//i.test(value) ? value : `https://${value}`
    if (!value.trim() || bookmarks.includes(normalized)) return
    const next = [normalized, ...bookmarks].slice(0, 20)
    setBookmarks(next); localStorage.setItem('jarvis_bookmarks', JSON.stringify(next))
  }

  const runCode = async () => {
    if (!value.trim() || !window.confirm('Execute this Python in Jarvis isolated mode?')) return
    setBusy(true); setError(''); setOutput('')
    try {
      const result = await api.executeCode(value, true)
      setOutput([result.stdout, result.stderr].filter(Boolean).join('\n') || `Process exited with code ${result.exit_code}`)
      onToast(`Python exited with code ${result.exit_code}`, result.exit_code === 0 ? 'good' : 'warn')
    } catch (runError: any) { setError(runError?.response?.data?.detail || 'Code execution failed') }
    finally { setBusy(false) }
  }

  const recommendTools = async () => {
    setBusy(true); setError('')
    try { setItems((await api.recommendNvidiaSkills(value || 'Jarvis desktop assistant automation', 12)).recommendations || []) }
    catch { setError('NVIDIA skill catalog is unavailable') }
    finally { setBusy(false) }
  }

  const pairBluetooth = async () => {
    const manager = (navigator as any).bluetooth
    if (!manager) { setError('Web Bluetooth is unavailable in this browser'); return }
    try {
      const device = await manager.requestDevice({ acceptAllDevices: true })
      bluetoothDevices.current.set(device.id, device)
      setItems(current => [{ id: device.id, name: device.name || 'Unnamed device', connected: Boolean(device.gatt?.connected) }, ...current.filter(item => item.id !== device.id)])
      onToast(`${device.name || 'Bluetooth device'} selected`, 'good')
    } catch (pairError: any) {
      if (pairError?.name !== 'NotFoundError') setError(pairError?.message || 'Bluetooth pairing failed')
    }
  }

  const toggleBluetooth = async (id: string) => {
    const device = bluetoothDevices.current.get(id)
    if (!device?.gatt) return
    try {
      if (device.gatt.connected) device.gatt.disconnect()
      else await device.gatt.connect()
      setItems(current => current.map(item => item.id === id ? { ...item, connected: device.gatt.connected } : item))
    } catch (connectionError: any) { setError(connectionError?.message || 'Bluetooth connection failed') }
  }

  const saveSettings = async () => {
    setBusy(true); setError('')
    try { await api.saveDashboardPreferences(preferences); onToast('Settings saved', 'good') }
    catch { setError('Settings could not be saved') }
    finally { setBusy(false) }
  }

  const icon = label === 'FILES' ? <FileSearch /> : label === 'NOTES' ? <FileText /> : label === 'BROWSER' ? <Globe2 /> : label === 'CODE' ? <Code2 /> : label === 'TASKS' ? <Check /> : label === 'TOOLS' ? <Wrench /> : label === 'BLUETOOTH' ? <Bluetooth /> : <Settings />

  return <div className="workspace-panel">
    <div className="workspace-heading"><span>{icon}</span><div><h3>{label}</h3><p>{workspaceCopy[label] || 'Jarvis workspace controls.'}</p></div><button onClick={() => void load()} aria-label={`Refresh ${label}`}><RefreshCw className={busy ? 'spin' : ''} /></button></div>
    {error && <div className="workspace-error">{error}</div>}

    {label === 'FILES' && <><div className="workspace-toolbar"><input value={value} onChange={event => setValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') void searchFiles() }} placeholder="Filename or path…" /><button onClick={() => void searchFiles()}><Search />SEARCH</button></div><div className="workspace-split"><div className="workspace-list">{items.map(item => <article key={item.path}><button className="workspace-item-main" onClick={() => void previewFile(item.path)}><strong>{item.name}</strong><small>{item.path} · {item.size} bytes</small></button><button aria-label={`Open ${item.name}`} onClick={() => void api.openFile(item.path).then(() => onToast('File opened', 'good')).catch(() => setError('File could not be opened'))}><ExternalLink /></button></article>)}</div><pre className="workspace-output">{output || 'Select a file to preview it.'}</pre></div></>}

    {label === 'NOTES' && <><div className="workspace-compose"><textarea value={value} onChange={event => setValue(event.target.value)} placeholder="Write a persistent note…" /><button onClick={() => void saveNote()} disabled={busy}><Save />SAVE NOTE</button></div><div className="workspace-card-grid">{items.map(note => <article key={note.id}><time>{new Date(note.created_at * 1000).toLocaleString()}</time><p>{note.content}</p><button aria-label="Delete note" onClick={() => void api.deleteNote(note.id).then(load)}><Trash2 /></button></article>)}</div></>}

    {label === 'BROWSER' && <><div className="workspace-toolbar"><input value={value} onChange={event => setValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') void openUrl() }} placeholder="https://…" /><button onClick={() => void openUrl()}><ExternalLink />OPEN</button><button onClick={addBookmark} aria-label="Bookmark URL"><BookmarkPlus /></button></div><div className="workspace-list">{bookmarks.map(url => <article key={url}><button className="workspace-item-main" onClick={() => void openUrl(url)}><strong>{url}</strong><small>BOOKMARK</small></button><button aria-label="Delete bookmark" onClick={() => { const next = bookmarks.filter(item => item !== url); setBookmarks(next); localStorage.setItem('jarvis_bookmarks', JSON.stringify(next)) }}><Trash2 /></button></article>)}</div></>}

    {label === 'CODE' && <><div className="workspace-codebar"><span><Code2 />PYTHON · ISOLATED · 10S LIMIT</span><button onClick={() => setValue("print('JARVIS code executor online')\nfor number in range(1, 6):\n    print(number, number ** 2)")}>LOAD SAMPLE</button><button onClick={() => { setValue(''); setOutput('') }}>CLEAR</button></div><textarea className="workspace-editor" value={value} onChange={event => setValue(event.target.value)} spellCheck={false} placeholder="# Enter Python code…" /><button className="workspace-primary" onClick={() => void runCode()} disabled={busy}><Play />RUN CONFIRMED CODE</button><pre className="workspace-output code-output">{output || 'Execution output appears here.'}</pre></>}

    {label === 'TASKS' && <><div className="workspace-toolbar"><input value={value} onChange={event => setValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') void createTask() }} placeholder="New task…" /><select value={priority} onChange={event => setPriority(event.target.value)}><option>low</option><option>medium</option><option>high</option></select><button onClick={() => void createTask()}><Save />ADD</button></div><div className="workspace-list">{items.map(task => <article className={task.completed ? 'completed' : ''} key={task.id}><button aria-label={task.completed ? 'Mark incomplete' : 'Mark complete'} onClick={() => void api.updateTask(task.id, { completed: !task.completed }).then(load)}>{task.completed ? <Check /> : <span className="task-ring" />}</button><button className="workspace-item-main" onClick={() => void api.updateTask(task.id, { priority: task.priority === 'high' ? 'low' : task.priority === 'low' ? 'medium' : 'high' }).then(load)}><strong>{task.title}</strong><small>{task.priority.toUpperCase()} PRIORITY</small></button><button aria-label="Delete task" onClick={() => void api.deleteTask(task.id).then(load)}><Trash2 /></button></article>)}</div></>}

    {label === 'TOOLS' && <><div className="workspace-toolbar"><input value={value} onChange={event => setValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') void recommendTools() }} placeholder="Describe the capability you need…" /><button onClick={() => void recommendTools()}><Search />MATCH</button></div><div className="workspace-card-grid tools-grid">{items.map(tool => <article key={tool.name}><strong>{tool.name}</strong><small>{tool.product || tool.category || 'NVIDIA SKILL'}</small><p>{tool.description}</p><button onClick={() => onCommand(`Use the NVIDIA ${tool.name} skill for this task: ${value || tool.description}`)}><Send />USE WITH JARVIS</button></article>)}</div></>}

    {label === 'BLUETOOTH' && <><button className="workspace-primary" onClick={() => void pairBluetooth()}><Bluetooth />PAIR NEW DEVICE</button><p className="workspace-hint">Your browser will show the secure system device picker. Jarvis never receives Bluetooth credentials.</p><div className="workspace-list">{items.map(device => <article key={device.id}><span className={`device-dot ${device.connected ? 'online' : ''}`} /><button className="workspace-item-main" onClick={() => void toggleBluetooth(device.id)}><strong>{device.name}</strong><small>{device.connected ? 'CONNECTED' : 'AVAILABLE / PAIRED'}</small></button><button onClick={() => void toggleBluetooth(device.id)} aria-label={device.connected ? 'Disconnect device' : 'Connect device'}>{device.connected ? <Unplug /> : <PlugZap />}</button></article>)}</div></>}

    {label === 'SETTINGS' && <><div className="settings-grid"><label><span>AUTO MICROPHONE</span><input type="checkbox" checked={preferences.auto_mic} onChange={event => setPreferences(current => ({ ...current, auto_mic: event.target.checked }))} /></label><label><span>CLEAR WAKE SIGNAL</span><input type="checkbox" checked={preferences.clear_wake} onChange={event => setPreferences(current => ({ ...current, clear_wake: event.target.checked }))} /></label><label><span>OWNER VOICE ONLY</span><input type="checkbox" checked={preferences.owner_voice_only} onChange={event => setPreferences(current => ({ ...current, owner_voice_only: event.target.checked }))} /></label><label className="range-setting"><span>MIC SENSITIVITY · {preferences.sensitivity}</span><input type="range" min="0" max="10" value={preferences.sensitivity} onChange={event => setPreferences(current => ({ ...current, sensitivity: Number(event.target.value) }))} /></label><label><span>STARTUP INTERFACE</span><select value={preferences.ui_preference} onChange={event => setPreferences(current => ({ ...current, ui_preference: event.target.value }))}><option value="dashboard">Dashboard</option><option value="voice">Voice Only</option></select></label></div><button className="workspace-primary" onClick={() => void saveSettings()} disabled={busy}><Save />SAVE ALL SETTINGS</button></>}

    {busy && <div className="workspace-loading"><Loader2 className="spin" />WORKING…</div>}
  </div>
}

export default WorkspacePanel
