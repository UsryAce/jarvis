import { memo, useCallback, useMemo, useState } from 'react'
import {
  Activity, Bot, BrainCircuit, CheckCircle2, CircleDashed, Code2,
  FlaskConical, GitMerge, Loader2, Network, Play, RefreshCw,
  Search, ShieldCheck, Square, TerminalSquare, Users,
} from 'lucide-react'
import './AgentSwarmPanel.css'

export type AgentCollaborationMode = 'cowork' | 'council' | 'swarm'
export type SwarmRecord = Record<string, unknown>

export interface AgentSwarmPanelProps {
  swarm?: SwarmRecord | null
  runtime?: SwarmRecord | null
  mode: AgentCollaborationMode
  maxAgents: number
  onModeChange: (mode: AgentCollaborationMode) => void
  onMaxAgentsChange: (count: number) => void
  onStart: (goal: string) => void | Promise<void>
  onCancel: () => void | Promise<void>
  onRefresh: () => void | Promise<void>
  onIntegrate: () => void | Promise<void>
  onRejectIntegration: () => void | Promise<void>
}

type AgentState = 'active' | 'queued' | 'done' | 'error' | 'idle'
type DisplayAgent = { id: string; name: string; role: string; model: string; status: AgentState; task: string }
type DisplayTask = { id: string; title: string; status: AgentState; dependencies: string[]; owner: string }

const specialists = [
  { id: 'manager', name: 'JARVIS MANAGER', role: 'Orchestration', icon: BrainCircuit },
  { id: 'designer', name: 'DESIGNER', role: 'Interface and experience', icon: Network },
  { id: 'coder', name: 'CODER', role: 'Implementation', icon: Code2 },
  { id: 'researcher', name: 'RESEARCHER', role: 'Evidence', icon: Search },
  { id: 'tester', name: 'TESTER', role: 'Verification', icon: FlaskConical },
  { id: 'reviewer', name: 'REVIEWER', role: 'Quality gate', icon: ShieldCheck },
  { id: 'devops', name: 'DEVOPS', role: 'Runtime', icon: TerminalSquare },
  { id: 'judge', name: 'JUDGE', role: 'Final decision', icon: GitMerge },
] as const

const isRecord = (value: unknown): value is SwarmRecord => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const textValue = (value: unknown, fallback = '') => typeof value === 'string' || typeof value === 'number' ? String(value) : fallback
const arrayValue = (value: unknown): unknown[] => Array.isArray(value) ? value : []
const stateValue = (value: unknown): AgentState => {
  const state = textValue(value).toLowerCase()
  if (['running', 'working', 'active', 'executing'].includes(state)) return 'active'
  if (['queued', 'pending', 'waiting', 'blocked'].includes(state)) return 'queued'
  if (['complete', 'completed', 'done', 'success', 'succeeded'].includes(state)) return 'done'
  if (['error', 'failed', 'cancelled', 'canceled'].includes(state)) return 'error'
  return 'idle'
}

function normalizeAgents(swarm?: SwarmRecord | null): DisplayAgent[] {
  const raw = arrayValue(swarm?.agents ?? swarm?.workers)
  return specialists.map((specialist, index) => {
    const match = raw.find((item) => isRecord(item) && [item.id, item.role, item.name]
      .some((value) => textValue(value).toLowerCase().includes(specialist.id)))
    const item = isRecord(match) ? match : isRecord(raw[index]) ? raw[index] : {}
    return {
      id: textValue(item.id, specialist.id),
      name: textValue(item.name, specialist.name).toUpperCase(),
      role: textValue(item.role, specialist.role),
      model: textValue(item.model ?? item.model_name, 'AUTO ROUTE'),
      status: stateValue(item.status ?? item.state),
      task: textValue(item.task ?? item.current_task ?? item.assignment, 'Awaiting assignment'),
    }
  })
}

function normalizeTasks(swarm?: SwarmRecord | null): DisplayTask[] {
  return arrayValue(swarm?.tasks ?? swarm?.task_graph).flatMap((value, index) => {
    if (!isRecord(value)) return []
    const dependencies = arrayValue(value.dependencies ?? value.depends_on).map((item) => textValue(item)).filter(Boolean)
    return [{
      id: textValue(value.id, `task-${index + 1}`),
      title: textValue(value.title ?? value.goal ?? value.description, `Task ${index + 1}`),
      status: stateValue(value.status ?? value.state),
      dependencies,
      owner: textValue(value.owner ?? value.agent ?? value.assignee, 'Unassigned'),
    }]
  })
}

const StatusGlyph = memo(function StatusGlyph({ status }: { status: AgentState }) {
  if (status === 'active') return <Loader2 className="swarm-spin" aria-hidden="true" />
  if (status === 'done') return <CheckCircle2 aria-hidden="true" />
  if (status === 'error') return <Square aria-hidden="true" />
  return <CircleDashed aria-hidden="true" />
})

function AgentSwarmPanel({
  swarm, runtime, mode, maxAgents, onModeChange, onMaxAgentsChange,
  onStart, onCancel, onRefresh, onIntegrate, onRejectIntegration,
}: AgentSwarmPanelProps) {
  const [goal, setGoal] = useState('')
  const agents = useMemo(() => normalizeAgents(swarm), [swarm])
  const tasks = useMemo(() => normalizeTasks(swarm), [swarm])
  const events = useMemo(() => arrayValue(swarm?.events ?? runtime?.events).slice(-12).reverse(), [swarm, runtime])
  const results = useMemo(() => arrayValue(swarm?.results ?? swarm?.artifacts).slice(-8), [swarm])
  const overallState = stateValue(swarm?.status ?? swarm?.state)
  const activeCount = agents.filter((agent) => agent.status === 'active').length
  const runtimeOnline = runtime?.healthy !== false && runtime?.online !== false
  const workerCount = textValue(runtime?.active_workers ?? runtime?.workers, String(activeCount))
  const queueDepth = textValue(runtime?.queue_depth ?? runtime?.queued, String(tasks.filter((task) => task.status === 'queued').length))
  const workspaceMode = textValue(swarm?.workspace_mode, 'direct')
  const integrationStatus = textValue(swarm?.integration_status, 'not_applicable')
  const worktreeBranch = textValue(swarm?.worktree_branch, 'DIRECT PROJECT ROOT')
  const changes = isRecord(swarm?.changes) ? swarm.changes : {}
  const changedFiles = arrayValue(changes.changed_files ?? changes.files)
  const isTerminal = ['done', 'error'].includes(overallState)
  const canIntegrate = workspaceMode === 'worktree' && integrationStatus === 'pending' && isTerminal
  const canDiscard = workspaceMode === 'worktree' && !['integrated', 'rejected'].includes(integrationStatus) && isTerminal

  const submit = useCallback(() => {
    const nextGoal = goal.trim()
    if (!nextGoal) return
    void onStart(nextGoal)
  }, [goal, onStart])

  return (
    <section className="agent-swarm" aria-label="Jarvis multi-agent command center">
      <header className="agent-swarm__header">
        <div>
          <span className="agent-swarm__eyebrow"><Network aria-hidden="true" /> MULTI-AGENT ORCHESTRATOR</span>
          <h2>JARVIS SWARM CONTROL</h2>
        </div>
        <div className={`agent-swarm__health ${runtimeOnline ? 'is-online' : 'is-error'}`} role="status">
          <Activity aria-hidden="true" /> {runtimeOnline ? 'RUNTIME ONLINE' : 'RUNTIME DEGRADED'}
        </div>
      </header>

      <div className="agent-swarm__toolbar">
        <fieldset className="agent-swarm__modes">
          <legend>COLLABORATION MODE</legend>
          {(['cowork', 'council', 'swarm'] as const).map((item) => (
            <button key={item} type="button" className={mode === item ? 'is-selected' : ''}
              aria-pressed={mode === item} onClick={() => onModeChange(item)}>
              {item === 'cowork' ? <Users aria-hidden="true" /> : item === 'council' ? <BrainCircuit aria-hidden="true" /> : <Network aria-hidden="true" />}
              {item.toUpperCase()}
            </button>
          ))}
        </fieldset>
        <label className="agent-swarm__concurrency">
          <span>CONCURRENCY <b>{Math.min(8, Math.max(2, maxAgents))}</b></span>
          <input type="range" min="2" max="8" step="1" value={Math.min(8, Math.max(2, maxAgents))}
            onChange={(event) => onMaxAgentsChange(Number(event.target.value))} aria-label="Maximum concurrent agents" />
        </label>
        <div className="agent-swarm__metrics" aria-label="Runtime statistics">
          <span><b>{workerCount}</b> ACTIVE</span>
          <span><b>{queueDepth}</b> QUEUED</span>
          <span><b>{textValue(runtime?.uptime, '--')}</b> UPTIME</span>
        </div>
        <button type="button" className="agent-swarm__icon-button" onClick={() => void onRefresh()} aria-label="Refresh swarm status">
          <RefreshCw aria-hidden="true" />
        </button>
      </div>

      <div className={`agent-swarm__workspace agent-swarm__workspace--${workspaceMode}`}>
        <GitMerge aria-hidden="true" />
        <span>
          <strong>{workspaceMode === 'worktree' ? 'ISOLATED GIT WORKTREE' : 'DIRECT PROJECT WORKSPACE'}</strong>
          <small>{worktreeBranch} · {changedFiles.length} CHANGED FILES</small>
        </span>
        <b>{integrationStatus.split('_').join(' ').toUpperCase()}</b>
        {textValue(swarm?.integration_error) && <em title={textValue(swarm?.integration_error)}>SAFETY GATE DETAILS</em>}
        <button type="button" onClick={() => void onIntegrate()} disabled={!canIntegrate}>INTEGRATE</button>
        <button type="button" className="is-danger" onClick={() => void onRejectIntegration()} disabled={!canDiscard}>REJECT</button>
      </div>

      <div className="agent-swarm__command">
        <label htmlFor="jarvis-swarm-goal">MISSION DIRECTIVE</label>
        <div>
          <textarea id="jarvis-swarm-goal" value={goal} onChange={(event) => setGoal(event.target.value)}
            placeholder="Give the council a goal, project, or multi-step mission..." rows={2} />
          <button type="button" onClick={submit} disabled={!goal.trim() || overallState === 'active'}>
            <Play aria-hidden="true" /> DEPLOY
          </button>
          <button type="button" className="is-danger" onClick={() => void onCancel()} disabled={!['active', 'queued'].includes(overallState)}>
            <Square aria-hidden="true" /> ABORT
          </button>
        </div>
      </div>

      <div className="agent-swarm__agents" aria-label="Specialist agents">
        {agents.map((agent, index) => {
          const Icon = specialists[index].icon
          return (
            <article className={`swarm-agent swarm-agent--${agent.status}`} key={agent.id}>
              <div className="swarm-agent__icon"><Icon aria-hidden="true" /></div>
              <div className="swarm-agent__identity"><h3>{agent.name}</h3><span>{agent.role}</span></div>
              <span className={`swarm-state swarm-state--${agent.status}`}><StatusGlyph status={agent.status} />{agent.status.toUpperCase()}</span>
              <p title={agent.task}>{agent.task}</p>
              <small><Bot aria-hidden="true" /> {agent.model}</small>
            </article>
          )
        })}
      </div>

      <div className="agent-swarm__lower">
        <section className="swarm-data-panel" aria-labelledby="swarm-task-heading">
          <h3 id="swarm-task-heading">TASK DEPENDENCY GRAPH <span>{tasks.length}</span></h3>
          <div className="swarm-data-panel__scroll">
            {tasks.length ? tasks.map((task) => (
              <article className={`swarm-task swarm-task--${task.status}`} key={task.id}>
                <StatusGlyph status={task.status} />
                <div><b>{task.title}</b><span>{task.owner} · {task.dependencies.length ? `WAITING ON ${task.dependencies.join(', ')}` : 'READY'}</span></div>
              </article>
            )) : <p className="swarm-empty">No mission graph. Deploy a directive to generate parallel tasks.</p>}
          </div>
        </section>

        <section className="swarm-data-panel" aria-labelledby="swarm-events-heading">
          <h3 id="swarm-events-heading">LIVE EVENT BUS <span>{events.length}</span></h3>
          <div className="swarm-data-panel__scroll" aria-live="polite">
            {events.length ? events.map((event, index) => {
              const item = isRecord(event) ? event : {}
              return <p className="swarm-event" key={textValue(item.id, String(index))}>
                <time>{textValue(item.time ?? item.timestamp, '--:--')}</time>
                <span>{textValue(item.message ?? item.event ?? item.type, textValue(event))}</span>
              </p>
            }) : <p className="swarm-empty">Event stream standing by.</p>}
          </div>
        </section>

        <section className="swarm-data-panel" aria-labelledby="swarm-results-heading">
          <h3 id="swarm-results-heading">RESULTS &amp; ARTIFACTS <span>{results.length}</span></h3>
          <div className="swarm-data-panel__scroll">
            {results.length ? results.map((result, index) => {
              const item = isRecord(result) ? result : {}
              return <article className="swarm-result" key={textValue(item.id, String(index))}>
                <CheckCircle2 aria-hidden="true" /><div><b>{textValue(item.title ?? item.name, `Result ${index + 1}`)}</b><span>{textValue(item.summary ?? item.output ?? item.path, textValue(result))}</span></div>
              </article>
            }) : <p className="swarm-empty">Validated outputs will appear here.</p>}
          </div>
        </section>
      </div>
    </section>
  )
}

export default memo(AgentSwarmPanel)
