/* JARVIS data adapter — the single seam between this interface and the real backend.
 *
 * The UI reads ONLY the canonical view model described below. Nothing in the
 * interface invents values when live data is present; when it is absent every
 * affected panel is flagged DEMO in the chrome.
 *
 * Load with:  <script src="./jarvis-adapter.js"></script>   (sets window.JarvisAdapter)
 *
 * ───────────────────────────── canonical view model ─────────────────────────
 * Snapshot {
 *   at: string                       ISO timestamp the snapshot was produced
 *   source: 'live' | 'demo'
 *   agent: {
 *     state: AgentState              see STATE_ENUM
 *     detail: string                 one short line, no chain-of-thought
 *     since: string                  ISO
 *     autonomy: 1|2|3|4              1 ask, 2 assisted, 3 trusted workspace, 4 autopilot
 *     held: boolean                  emergency stop / operator hold active
 *   }
 *   telemetry: {
 *     uptimeSec: number, cpuPct: number, ramPct: number, gpuPct: number,
 *     diskPct: number, netUpMbs: number, netDownMbs: number
 *   }
 *   session: { id, startedAt, durationSec, route, messages }
 *   workspace: { project, branch, dirtyFiles, budgetMin, agentsActive, agentsTotal,
 *                tasksComplete, tasksTotal, missionWindow }
 *   flow: [{ name, state, tone }]            the OPERATIONS FLOW chips, in order
 *   graph: { nodes, edges, vaultNotes, health }   BRAIN GRAPH rail counters
 *   router: {
 *     auto: boolean, primary: string,
 *     models: [{ id, name, provider, variants, health: Health, latencyMs,
 *                selectable, catalogSource }]
 *   }
 *   providers: [{ id, name, status: Health, latencyMs, circuit: 'closed'|'open'|'half' }]
 *   voice: { armed, inputDevice, outputDevice, profile, sensitivity, level: number 0..1 }
 *   usage: { requests, tokens, spendUsd, capUsd, series:[{t,v}] }   series = 24h sparkline
 *   events: [{ at, who, meta, text, level: 'info'|'warn'|'error' }]
 *   capabilities: [{ id, label, state: CapabilityState, summary,
 *                    evidence:[{source,detail}] }]
 *   screens: { [ScreenKey]: Screen }
 *   viz: { [ScreenKey]: Viz }
 * }
 *
 * Screen { title, subtitle, kpis: [{k,v,tone}], items: [Item] }
 * Item   { name, sub, tag, tone, pct, meta: [[k,v],[k,v]], action?: {id,command,payload,confirm} }
 * tone   'ok' | 'info' | 'warn' | 'danger' | 'muted'   → the UI owns the colours
 *
 * Viz is one of:
 *   { kind:'graph',    nodes:[{id,x,y,z,cluster,size,label}], edges:[[i,j]] }   x,y,z ∈ [-1,1]
 *   { kind:'topology', hub:{label,state}, spokes:[{label,state,ring}] }
 *   { kind:'series',   points:[{t,v}], compare:[{t,v}]|null, unit, axis:[string] }
 *
 * AgentState: see STATE_ENUM. Health: 'healthy'|'degraded'|'down'|'unknown'.
 * CapabilityState: 'available'|'configured'|'verified'|'degraded'|'unavailable'.
 * ScreenKey:  see SCREEN_KEYS.
 */
(function () {
  var STATE_ENUM = ['idle', 'listening', 'transcribing', 'thinking', 'delegating',
    'executing', 'testing', 'speaking', 'awaiting_approval', 'paused', 'degraded',
    'completed', 'error'];

  var SCREEN_KEYS = ['DASHBOARD', 'CHAT', 'VOICE', 'MISSIONS', 'AGENTS', 'PROJECTS',
    'FILES', 'NOTES', 'BROWSER', 'CODE', 'BRAIN', 'TASKS', 'TOOLS', 'AUTOMATIONS',
    'GIT', 'SECURITY', 'USAGE', 'DEVICES', 'SETTINGS'];

  var TONES = ['ok', 'info', 'warn', 'danger', 'muted'];
  var CAPABILITY_STATES = ['available', 'configured', 'verified', 'degraded', 'unavailable'];

  /* Endpoints the adapter will call. Rename here only — the UI never sees URLs. */
  var EXPECTED_ENDPOINTS = {
    snapshot: '/api/ui/snapshot',      // GET  → Snapshot (whole view model)
    stream: '/ws/ui',                  // WS   → { type:'snapshot', value:Snapshot }
    screen: '/api/ui/screen/{key}',    // GET  → Screen (lazy, per tab)
    viz: '/api/ui/viz/{key}',          // GET  → Viz
    command: '/api/ui/command',        // POST { action, payload } → { ok, message }
    approve: '/api/ui/approval/{id}'   // POST { decision:'approve'|'reject', note }
  };

  function num(v, d) { v = Number(v); return isFinite(v) ? v : (d || 0); }
  function str(v, d) { return typeof v === 'string' && v.length ? v : (d || ''); }
  function tone(v) { return TONES.indexOf(v) >= 0 ? v : 'info'; }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function obj(v) { return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; }

  /* Coerce whatever the backend sends into the canonical model. Never throws:
     it returns { data, problems } so the UI can show a degraded, honest state. */
  function normalize(raw) {
    var problems = [];
    if (!raw || typeof raw !== 'object') return { data: null, problems: ['empty payload'] };
    ['providers', 'flow', 'events', 'capabilities'].forEach(function (key) {
      if (raw[key] != null && !Array.isArray(raw[key])) problems.push(key + ' must be an array');
    });
    if (raw.router && raw.router.models != null && !Array.isArray(raw.router.models)) {
      problems.push('router.models must be an array');
    }

    var a = raw.agent || {};
    var state = STATE_ENUM.indexOf(a.state) >= 0 ? a.state : (problems.push('unknown agent.state: ' + a.state), 'idle');

    var t = raw.telemetry || {};
    var data = {
      at: str(raw.at, new Date().toISOString()),
      source: 'live',
      agent: {
        state: state, detail: str(a.detail), since: str(a.since),
        autonomy: Math.min(4, Math.max(1, num(a.autonomy, 2))), held: !!a.held
      },
      telemetry: {
        uptimeSec: num(t.uptimeSec), cpuPct: num(t.cpuPct), ramPct: num(t.ramPct),
        gpuPct: num(t.gpuPct), diskPct: num(t.diskPct),
        netUpMbs: num(t.netUpMbs), netDownMbs: num(t.netDownMbs)
      },
      session: raw.session ? {
        id: str(raw.session.id), startedAt: str(raw.session.startedAt),
        durationSec: num(raw.session.durationSec), route: str(raw.session.route),
        messages: num(raw.session.messages)
      } : null,
      router: raw.router ? {
        auto: !!raw.router.auto, primary: str(raw.router.primary),
        capabilityState: CAPABILITY_STATES.indexOf(raw.router.capabilityState) >= 0
          ? raw.router.capabilityState : 'unavailable',
        evidence: arr(raw.router.evidence).slice(0, 6).map(function (e) {
          e = obj(e);
          return { source: str(e.source), detail: str(e.detail) };
        }),
        models: arr(raw.router.models).map(function (m) {
          m = obj(m);
          return {
            id: str(m.id), name: str(m.name, m.id), provider: str(m.provider),
            variants: num(m.variants, 1), health: str(m.health, 'unknown'), latencyMs: num(m.latencyMs),
            selectable: m.selectable === true, catalogSource: str(m.catalogSource, 'configured'),
            capabilityState: CAPABILITY_STATES.indexOf(m.capabilityState) >= 0
              ? m.capabilityState : 'unavailable',
            evidenceSource: str(m.evidenceSource, 'unavailable')
          };
        })
      } : null,
      providers: arr(raw.providers).map(function (p) {
        p = obj(p);
        return {
          id: str(p.id), name: str(p.name, p.id), status: str(p.status, 'unknown'),
          latencyMs: num(p.latencyMs), latencyVerified: p.latencyVerified === true,
          circuit: str(p.circuit, 'unknown'),
          capabilityState: CAPABILITY_STATES.indexOf(p.capabilityState) >= 0
            ? p.capabilityState : 'unavailable',
          evidence: arr(p.evidence).slice(0, 6).map(function (e) {
            e = obj(e);
            return { source: str(e.source), detail: str(e.detail) };
          })
        };
      }),
      voice: raw.voice ? {
        armed: !!raw.voice.armed, inputDevice: str(raw.voice.inputDevice),
        outputDevice: str(raw.voice.outputDevice), profile: str(raw.voice.profile),
        sensitivity: num(raw.voice.sensitivity, 6), level: num(raw.voice.level),
        capabilityState: CAPABILITY_STATES.indexOf(raw.voice.capabilityState) >= 0
          ? raw.voice.capabilityState : 'unavailable'
      } : null,
      usage: raw.usage ? {
        requests: num(raw.usage.requests), tokens: num(raw.usage.tokens),
        spendUsd: num(raw.usage.spendUsd), capUsd: num(raw.usage.capUsd),
        metered: raw.usage.metered === true,
        series: arr(raw.usage.series).map(function (p) { p = obj(p); return { t: str(p.t), v: num(p.v) }; })
      } : null,
      workspace: raw.workspace ? {
        project: str(raw.workspace.project), branch: str(raw.workspace.branch),
        dirtyFiles: num(raw.workspace.dirtyFiles), budgetMin: num(raw.workspace.budgetMin),
        agentsActive: num(raw.workspace.agentsActive), agentsTotal: num(raw.workspace.agentsTotal),
        tasksComplete: num(raw.workspace.tasksComplete), tasksTotal: num(raw.workspace.tasksTotal),
        missionWindow: str(raw.workspace.missionWindow),
        projects: arr(raw.workspace.projects).map(function (p) {
          p = obj(p);
          return { id: str(p.id), name: str(p.name, p.id), protected: p.protected === true };
        })
      } : null,
      flow: arr(raw.flow).map(function (f) {
        f = obj(f);
        return { name: str(f.name), state: str(f.state), tone: tone(f.tone) };
      }),
      graph: raw.graph ? {
        nodes: num(raw.graph.nodes), edges: num(raw.graph.edges),
        vaultNotes: num(raw.graph.vaultNotes), health: str(raw.graph.health, 'unknown')
      } : null,
      events: arr(raw.events).map(function (e) {
        e = obj(e);
        return {
          at: str(e.at), who: str(e.who, 'SYSTEM'), meta: str(e.meta),
          text: str(e.text), level: ['info', 'warn', 'error'].indexOf(e.level) >= 0 ? e.level : 'info'
        };
      }),
      capabilities: arr(raw.capabilities).map(function (c) {
        c = obj(c);
        var state = CAPABILITY_STATES.indexOf(c.state) >= 0 ? c.state : 'unavailable';
        if (state !== c.state) problems.push('unknown capability state for ' + str(c.id, 'unknown'));
        return {
          id: str(c.id), label: str(c.label, c.id), state: state,
          summary: str(c.summary),
          evidence: arr(c.evidence).slice(0, 6).map(function (e) {
            e = obj(e);
            return { source: str(e.source), detail: str(e.detail) };
          })
        };
      }),
      screens: {}, viz: {}
    };

    Object.keys(raw.screens || {}).forEach(function (k) {
      if (SCREEN_KEYS.indexOf(k) < 0) { problems.push('unknown screen key: ' + k); return; }
      var s = obj(raw.screens[k]);
      data.screens[k] = {
        title: str(s.title, k), subtitle: str(s.subtitle),
        kpis: arr(s.kpis).slice(0, 4).map(function (x) { x = obj(x); return { k: str(x.k), v: str(x.v), tone: tone(x.tone) }; }),
        items: arr(s.items).map(function (i) {
          i = obj(i);
          var action = i.action && typeof i.action === 'object' ? i.action : null;
          return {
            name: str(i.name), sub: str(i.sub), tag: str(i.tag), tone: tone(i.tone),
            pct: num(i.pct), meta: arr(i.meta).slice(0, 2).map(function (m) { m = arr(m); return [str(m[0]), str(m[1])]; }),
            action: action ? {
              id: str(action.id, str(i.id)),
              command: str(action.command), payload: action.payload && typeof action.payload === 'object' ? action.payload : {},
              confirm: str(action.confirm)
            } : null
          };
        })
      };
    });

    Object.keys(raw.viz || {}).forEach(function (k) {
      var v = obj(raw.viz[k]); if (!Object.keys(v).length || SCREEN_KEYS.indexOf(k) < 0) return;
      if (v.kind === 'graph') {
        data.viz[k] = {
          kind: 'graph',
          nodes: arr(v.nodes).map(function (n) {
            n = obj(n);
            return { id: str(n.id), x: num(n.x), y: num(n.y), z: num(n.z), cluster: num(n.cluster), size: num(n.size, 1), label: str(n.label) };
          }),
          edges: arr(v.edges).filter(function (e) { return e && e.length >= 2; })
        };
      } else if (v.kind === 'topology') {
        data.viz[k] = {
          kind: 'topology',
          hub: { label: str((v.hub || {}).label, 'ORCHESTRATOR'), state: str((v.hub || {}).state, 'idle') },
          spokes: arr(v.spokes).map(function (s) { s = obj(s); return { label: str(s.label), state: str(s.state, 'idle'), ring: num(s.ring, 1) }; })
        };
      } else if (v.kind === 'series') {
        data.viz[k] = {
          kind: 'series', unit: str(v.unit),
          points: arr(v.points).map(function (p) { p = obj(p); return { t: str(p.t), v: num(p.v) }; }),
          compare: Array.isArray(v.compare) ? v.compare.map(function (p) { p = obj(p); return { t: str(p.t), v: num(p.v) }; }) : null,
          axis: arr(v.axis).map(String)
        };
      } else problems.push('unknown viz kind for ' + k + ': ' + v.kind);
    });

    return { data: data, problems: problems };
  }

  /* Connect. Polls the snapshot and, when available, upgrades to the websocket.
     onChange(snapshotOrNull, meta) fires on every accepted update and on failure,
     so the UI can flip a panel to DEMO instead of showing stale numbers. */
  function connect(opts) {
    opts = opts || {};
    var base = (opts.baseUrl || (window.location && window.location.origin) || '').replace(/\/$/, '');
    var pollMs = Math.max(500, opts.pollMs || 2000);
    var onChange = opts.onChange || function () { };
    var alive = true, ws = null, wsReady = false, timer = null, failures = 0, reconnectTimer = null;
    var lastSnapshot = null, commandSequence = 0, pendingCommands = {};

    function postHost(action, payload, requestId) {
      if (window.parent === window) return false;
      window.parent.postMessage({
        source: 'jarvis-design', action: action,
        payload: payload || {}, requestId: requestId || ''
      }, window.location.origin);
      return true;
    }

    function hostCommand(action, payload) {
      if (window.parent === window) return null;
      var requestId = 'exact-' + Date.now() + '-' + (++commandSequence);
      return new Promise(function (resolve) {
        var timeout = setTimeout(function () {
          delete pendingCommands[requestId];
          resolve({ ok: false, message: 'Command bridge timed out' });
        }, 30000);
        pendingCommands[requestId] = { resolve: resolve, timeout: timeout };
        postHost('command', { action: action, payload: payload || {} }, requestId);
      });
    }

    function hostApproval(id, decision, note, reference) {
      if (window.parent === window) return null;
      var requestId = 'exact-approval-' + Date.now() + '-' + (++commandSequence);
      return new Promise(function (resolve) {
        var timeout = setTimeout(function () {
          delete pendingCommands[requestId];
          resolve({ ok: false, message: 'Approval bridge timed out' });
        }, 30000);
        pendingCommands[requestId] = { resolve: resolve, timeout: timeout };
        reference = obj(reference);
        postHost('approval', {
          id: id, decision: decision, note: note || '',
          stepId: str(reference.stepId), challengeId: str(reference.challengeId),
          approvals: arr(reference.approvals)
        }, requestId);
      });
    }

    function onHostMessage(event) {
      if (event.origin !== window.location.origin || event.source !== window.parent) return;
      var message = event.data || {};
      if (message.source !== 'jarvis-host' || message.action !== 'command-result') return;
      var pending = pendingCommands[message.requestId];
      if (!pending) return;
      clearTimeout(pending.timeout);
      delete pendingCommands[message.requestId];
      pending.resolve(message.result && typeof message.result === 'object'
        ? message.result : { ok: false, message: 'Invalid command response' });
    }
    window.addEventListener('message', onHostMessage);

    function meta(extra) {
      return Object.assign({ baseUrl: base, transport: wsReady ? 'websocket' : 'poll', failures: failures }, extra || {});
    }

    function accept(raw) {
      var res = normalize(raw);
      if (!res.data) { fail('normalize: ' + res.problems.join('; ')); return; }
      failures = 0;
      lastSnapshot = res.data;
      onChange(res.data, meta({ problems: res.problems }));
    }

    function fail(reason) {
      failures++;
      var detail = String(reason);
      if (/HTTP\s+(401|403)\b/.test(detail)) postHost('session-expired', {});
      if (lastSnapshot) onChange(lastSnapshot, meta({ error: detail, stale: true }));
      else onChange(null, meta({ error: detail, connecting: failures < 3 }));
    }

    function poll() {
      if (!alive || !base || wsReady) return;
      fetch(base + EXPECTED_ENDPOINTS.snapshot, { credentials: 'same-origin', headers: { accept: 'application/json' } })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(accept)
        .catch(function (e) { fail(e.message || e); });
    }

    function openWs() {
      if (!base || typeof WebSocket === 'undefined') return;
      var url = base.replace(/^http/, 'ws') + EXPECTED_ENDPOINTS.stream;
      try { ws = new WebSocket(url); } catch (e) { ws = null; return; }
      ws.onopen = function () { wsReady = true; };
      ws.onmessage = function (ev) {
        try {
          var msg = JSON.parse(ev.data);
          if (msg.type === 'snapshot') accept(msg.value);
          else if (msg.type === 'patch' && opts.onPatch) opts.onPatch(msg.path, msg.value);
        } catch (e) { /* ignore malformed frame */ }
      };
      ws.onclose = function () {
        ws = null; wsReady = false;
        poll();
        if (!alive || reconnectTimer) return;
        reconnectTimer = setTimeout(function () {
          reconnectTimer = null;
          if (alive) openWs();
        }, Math.min(10000, 750 * Math.pow(2, Math.min(failures, 4))));
      };
      ws.onerror = function () { wsReady = false; try { ws.close(); } catch (e) { } ws = null; };
    }

    if (base) { poll(); openWs(); timer = setInterval(poll, pollMs); }
    else onChange(null, meta({ error: 'no baseUrl configured — running on demo data' }));

    function bounded(v, fallback, maxLength) {
      return typeof v === 'string' && v.length
        ? v.slice(0, maxLength || 512)
        : (fallback || '');
    }

    function safeFailureReceipt(raw, status) {
      raw = obj(raw);
      var failure = {
        ok: false,
        message: bounded(raw.message || raw.detail || raw.code, 'HTTP ' + status, 800)
      };
      if (typeof raw.code === 'string') failure.code = bounded(raw.code, '', 128);
      if (typeof raw.correlation_id === 'string') {
        failure.correlation_id = bounded(raw.correlation_id, '', 128);
      }
      if (raw.retryable === true || raw.retryable === false) failure.retryable = raw.retryable;
      if (Object.prototype.hasOwnProperty.call(raw, 'applied')) {
        failure.applied = raw.applied === true ? true : raw.applied === false ? false : null;
      }
      if (raw.partial === true || raw.partial === false) failure.partial = raw.partial;
      ['applied_count', 'requested_count'].forEach(function (key) {
        if (typeof raw[key] === 'number' && isFinite(raw[key])) {
          failure[key] = Math.max(0, Math.floor(raw[key]));
        }
      });
      failure.applied_ids = arr(raw.applied_ids).slice(0, 64).map(function (value) {
        return bounded(value, '', 192);
      }).filter(Boolean);
      failure.applied_items = arr(raw.applied_items).slice(0, 64).map(function (item) {
        item = obj(item);
        return {
          id: bounded(item.id, '', 192),
          agent_run_id: bounded(item.agent_run_id, '', 128),
          step_id: bounded(item.step_id, '', 80),
          status: bounded(item.status, 'unknown', 80)
        };
      });
      ['failed_approval_id', 'reason_code', 'swarm_id', 'swarm_status', 'status'].forEach(function (key) {
        if (typeof raw[key] === 'string') failure[key] = bounded(raw[key], '', 192);
      });
      failure.child_statuses = arr(raw.child_statuses).slice(0, 64).map(function (item) {
        item = obj(item);
        return {
          task_id: bounded(item.task_id, '', 128),
          task_status: bounded(item.task_status, 'unknown', 80),
          agent_run_id: bounded(item.agent_run_id, '', 128),
          agent_status: bounded(item.agent_status, 'unknown', 80)
        };
      });
      if (raw.reconciliation && typeof raw.reconciliation === 'object') {
        var reconciliation = obj(raw.reconciliation);
        failure.reconciliation = {
          required: reconciliation.required === true,
          action: bounded(reconciliation.action, 'refresh_before_retry', 80),
          guidance: bounded(reconciliation.guidance, 'Refresh status before retry.', 1200),
          resume_attempted: reconciliation.resume_attempted === true,
          resume_status: bounded(reconciliation.resume_status, 'unknown', 80),
          reason_code: bounded(reconciliation.reason_code, '', 128)
        };
      }
      return failure;
    }

    function securePost(path, body) {
      return fetch(base + '/api/auth/session', {
        credentials: 'same-origin', headers: { accept: 'application/json' }
      }).then(function (sessionResponse) {
        if (!sessionResponse.ok) throw new Error('Authentication required (HTTP ' + sessionResponse.status + ')');
        return sessionResponse.json();
      }).then(function (session) {
        return fetch(base + path, {
          method: 'POST', credentials: 'same-origin',
          headers: { 'content-type': 'application/json', 'X-Jarvis-CSRF': session.csrf_token },
          body: JSON.stringify(body)
        });
      }).then(function (r) {
        return r.json().then(function (body) {
          if (!r.ok) return safeFailureReceipt(body, r.status);
          return Object.assign({ ok: true }, body);
        });
      }).catch(function (e) { return { ok: false, message: String(e && e.message || e) }; });
    }

    return {
      dispose: function () {
        alive = false; clearInterval(timer); clearTimeout(reconnectTimer);
        window.removeEventListener('message', onHostMessage);
        Object.keys(pendingCommands).forEach(function (key) {
          clearTimeout(pendingCommands[key].timeout);
          pendingCommands[key].resolve({ ok: false, message: 'Command bridge closed' });
          delete pendingCommands[key];
        });
        if (ws) try { ws.close(); } catch (e) { }
      },
      command: function (action, payload) {
        payload = obj(payload);
        var runId = typeof payload.runId === 'string' ? payload.runId.trim() : '';
        var bridged = hostCommand(action, payload);
        if (bridged) return bridged;
        var protectedPath = null, protectedBody = {};
        if (runId) {
          var encoded = encodeURIComponent(runId);
          if (action === 'approve_agent_run') {
            if (!str(payload.stepId) || !str(payload.challengeId)) {
              return Promise.resolve({ ok: false, message: 'Approval challenge is missing; refresh the run card' });
            }
            protectedPath = '/api/ui/agent/runs/' + encoded + '/approve-current';
            protectedBody = { step_id: payload.stepId, challenge_id: payload.challengeId };
          }
          else if (action === 'cancel_agent_run') protectedPath = '/api/ui/agent/runs/' + encoded + '/cancel';
          else if (action === 'approve_swarm_run') {
            var approvals = arr(payload.approvals);
            if (!approvals.length) {
              return Promise.resolve({ ok: false, message: 'Swarm approval challenges are missing; refresh the mission card' });
            }
            protectedPath = '/api/ui/swarm/runs/' + encoded + '/approve-current';
            protectedBody = { approvals: approvals.map(function (item) {
              item = obj(item);
              return {
                agent_run_id: str(item.agentRunId),
                step_id: str(item.stepId),
                challenge_id: str(item.challengeId)
              };
            }) };
          }
          else if (action === 'cancel_swarm_run') protectedPath = '/api/ui/swarm/runs/' + encoded + '/cancel';
        }
        if (!base) return Promise.resolve({ ok: false, message: 'demo mode — no backend attached' });
        if (protectedPath) return securePost(protectedPath, protectedBody);
        return securePost(EXPECTED_ENDPOINTS.command, { action: action, payload: payload });
      },
      approval: function (id, decision, note, reference) {
        id = typeof id === 'string' ? id.trim() : '';
        decision = decision === 'reject' ? 'reject' : decision === 'approve' ? 'approve' : '';
        if (!id || !decision) return Promise.resolve({ ok: false, message: 'A valid approval id and decision are required' });
        reference = obj(reference);
        var bridged = hostApproval(id, decision, note, reference);
        if (bridged) return bridged;
        if (!base) return Promise.resolve({ ok: false, message: 'demo mode — no backend attached' });
        return securePost(EXPECTED_ENDPOINTS.approve.replace('{id}', encodeURIComponent(id)), {
          decision: decision, note: typeof note === 'string' ? note : '',
          step_id: str(reference.stepId) || null,
          challenge_id: str(reference.challengeId) || null,
          approvals: arr(reference.approvals).map(function (item) {
            item = obj(item);
            return {
              agent_run_id: str(item.agentRunId),
              step_id: str(item.stepId),
              challenge_id: str(item.challengeId)
            };
          })
        });
      },
      emergencyStop: function () {
        var bridged = hostCommand('emergency_stop', {});
        if (bridged) return bridged;
        if (!base) return Promise.resolve({ ok: false, message: 'demo mode — no backend attached' });
        return fetch(base + '/api/control', {
          credentials: 'same-origin', headers: { accept: 'application/json' }
        }).then(function (r) { if (!r.ok) throw new Error('Control state unavailable'); return r.json(); })
          .then(function (control) {
            return securePost('/api/control/emergency-stop', {
              scope_type: 'global', scope_id: 'global', expected_revision: control.revision,
              client_request_id: 'dashboard-' + Date.now(), reason_code: 'dashboard_emergency_stop'
            });
          }).catch(function (e) { return { ok: false, message: String(e && e.message || e) }; });
      }
    };
  }

  window.JarvisAdapter = {
    connect: connect, normalize: normalize,
    STATE_ENUM: STATE_ENUM, SCREEN_KEYS: SCREEN_KEYS, TONES: TONES,
    CAPABILITY_STATES: CAPABILITY_STATES,
    EXPECTED_ENDPOINTS: EXPECTED_ENDPOINTS
  };
})();
