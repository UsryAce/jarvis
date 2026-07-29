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

  /* Coerce whatever the backend sends into the canonical model. Never throws:
     it returns { data, problems } so the UI can show a degraded, honest state. */
  function normalize(raw) {
    var problems = [];
    if (!raw || typeof raw !== 'object') return { data: null, problems: ['empty payload'] };

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
        models: (raw.router.models || []).map(function (m) {
          return {
            id: str(m.id), name: str(m.name, m.id), provider: str(m.provider),
            variants: num(m.variants, 1), health: str(m.health, 'unknown'), latencyMs: num(m.latencyMs),
            selectable: m.selectable === true, catalogSource: str(m.catalogSource, 'configured')
          };
        })
      } : null,
      providers: (raw.providers || []).map(function (p) {
        return {
          id: str(p.id), name: str(p.name, p.id), status: str(p.status, 'unknown'),
          latencyMs: num(p.latencyMs), circuit: str(p.circuit, 'closed')
        };
      }),
      voice: raw.voice ? {
        armed: !!raw.voice.armed, inputDevice: str(raw.voice.inputDevice),
        outputDevice: str(raw.voice.outputDevice), profile: str(raw.voice.profile),
        sensitivity: num(raw.voice.sensitivity, 6), level: num(raw.voice.level)
      } : null,
      usage: raw.usage ? {
        requests: num(raw.usage.requests), tokens: num(raw.usage.tokens),
        spendUsd: num(raw.usage.spendUsd), capUsd: num(raw.usage.capUsd),
        metered: raw.usage.metered === true,
        series: (raw.usage.series || []).map(function (p) { return { t: str(p.t), v: num(p.v) }; })
      } : null,
      workspace: raw.workspace ? {
        project: str(raw.workspace.project), branch: str(raw.workspace.branch),
        dirtyFiles: num(raw.workspace.dirtyFiles), budgetMin: num(raw.workspace.budgetMin),
        agentsActive: num(raw.workspace.agentsActive), agentsTotal: num(raw.workspace.agentsTotal),
        tasksComplete: num(raw.workspace.tasksComplete), tasksTotal: num(raw.workspace.tasksTotal),
        missionWindow: str(raw.workspace.missionWindow),
        projects: (raw.workspace.projects || []).map(function (p) {
          return { id: str(p.id), name: str(p.name, p.id), protected: p.protected === true };
        })
      } : null,
      flow: (raw.flow || []).map(function (f) {
        return { name: str(f.name), state: str(f.state), tone: tone(f.tone) };
      }),
      graph: raw.graph ? {
        nodes: num(raw.graph.nodes), edges: num(raw.graph.edges),
        vaultNotes: num(raw.graph.vaultNotes), health: str(raw.graph.health, 'unknown')
      } : null,
      events: (raw.events || []).map(function (e) {
        return {
          at: str(e.at), who: str(e.who, 'SYSTEM'), meta: str(e.meta),
          text: str(e.text), level: ['info', 'warn', 'error'].indexOf(e.level) >= 0 ? e.level : 'info'
        };
      }),
      screens: {}, viz: {}
    };

    Object.keys(raw.screens || {}).forEach(function (k) {
      if (SCREEN_KEYS.indexOf(k) < 0) { problems.push('unknown screen key: ' + k); return; }
      var s = raw.screens[k] || {};
      data.screens[k] = {
        title: str(s.title, k), subtitle: str(s.subtitle),
        kpis: (s.kpis || []).slice(0, 4).map(function (x) { return { k: str(x.k), v: str(x.v), tone: tone(x.tone) }; }),
        items: (s.items || []).map(function (i) {
          var action = i.action && typeof i.action === 'object' ? i.action : null;
          return {
            name: str(i.name), sub: str(i.sub), tag: str(i.tag), tone: tone(i.tone),
            pct: num(i.pct), meta: (i.meta || []).slice(0, 2).map(function (m) { return [str(m[0]), str(m[1])]; }),
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
      var v = raw.viz[k]; if (!v || SCREEN_KEYS.indexOf(k) < 0) return;
      if (v.kind === 'graph') {
        data.viz[k] = {
          kind: 'graph',
          nodes: (v.nodes || []).map(function (n) {
            return { id: str(n.id), x: num(n.x), y: num(n.y), z: num(n.z), cluster: num(n.cluster), size: num(n.size, 1), label: str(n.label) };
          }),
          edges: (v.edges || []).filter(function (e) { return e && e.length >= 2; })
        };
      } else if (v.kind === 'topology') {
        data.viz[k] = {
          kind: 'topology',
          hub: { label: str((v.hub || {}).label, 'ORCHESTRATOR'), state: str((v.hub || {}).state, 'idle') },
          spokes: (v.spokes || []).map(function (s) { return { label: str(s.label), state: str(s.state, 'idle'), ring: num(s.ring, 1) }; })
        };
      } else if (v.kind === 'series') {
        data.viz[k] = {
          kind: 'series', unit: str(v.unit),
          points: (v.points || []).map(function (p) { return { t: str(p.t), v: num(p.v) }; }),
          compare: v.compare ? v.compare.map(function (p) { return { t: str(p.t), v: num(p.v) }; }) : null,
          axis: (v.axis || []).map(String)
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

    function hostApproval(id, decision, note) {
      if (window.parent === window) return null;
      var requestId = 'exact-approval-' + Date.now() + '-' + (++commandSequence);
      return new Promise(function (resolve) {
        var timeout = setTimeout(function () {
          delete pendingCommands[requestId];
          resolve({ ok: false, message: 'Approval bridge timed out' });
        }, 30000);
        pendingCommands[requestId] = { resolve: resolve, timeout: timeout };
        postHost('approval', { id: id, decision: decision, note: note || '' }, requestId);
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
          if (!r.ok) return { ok: false, message: body.detail || body.code || ('HTTP ' + r.status) };
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
        var runId = payload && typeof payload.runId === 'string' ? payload.runId.trim() : '';
        var bridged = hostCommand(action, payload || {});
        if (bridged) return bridged;
        var protectedPath = null;
        if (runId) {
          var encoded = encodeURIComponent(runId);
          if (action === 'approve_agent_run') protectedPath = '/api/ui/agent/runs/' + encoded + '/approve-current';
          else if (action === 'cancel_agent_run') protectedPath = '/api/ui/agent/runs/' + encoded + '/cancel';
          else if (action === 'approve_swarm_run') protectedPath = '/api/ui/swarm/runs/' + encoded + '/approve-current';
          else if (action === 'cancel_swarm_run') protectedPath = '/api/ui/swarm/runs/' + encoded + '/cancel';
        }
        if (!base) return Promise.resolve({ ok: false, message: 'demo mode — no backend attached' });
        if (protectedPath) return securePost(protectedPath, {});
        return securePost(EXPECTED_ENDPOINTS.command, { action: action, payload: payload || null });
      },
      approval: function (id, decision, note) {
        id = typeof id === 'string' ? id.trim() : '';
        decision = decision === 'reject' ? 'reject' : decision === 'approve' ? 'approve' : '';
        if (!id || !decision) return Promise.resolve({ ok: false, message: 'A valid approval id and decision are required' });
        var bridged = hostApproval(id, decision, note);
        if (bridged) return bridged;
        if (!base) return Promise.resolve({ ok: false, message: 'demo mode — no backend attached' });
        return securePost(EXPECTED_ENDPOINTS.approve.replace('{id}', encodeURIComponent(id)), {
          decision: decision, note: typeof note === 'string' ? note : ''
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
    EXPECTED_ENDPOINTS: EXPECTED_ENDPOINTS
  };
})();
