# JARVIS Mobile Access

The installable mobile command interface is available at `/mobile`. It shares the
desktop control plane: operator authentication, scoped permissions, CSRF protection,
Auto Mode, agent state, Brain state, chat, and voice controls are not duplicated or
weakened for mobile.

## Anywhere access (cellular or another Wi-Fi)

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-remote-mobile.ps1
```

The command prints an HTTPS `trycloudflare.com/mobile` URL. The
`JarvisAutonomous` scheduled supervisor keeps Jarvis and the tunnel alive, and
writes the current address to `data/mobile-access.json`. Quick-tunnel hostnames
rotate if the tunnel process restarts, so rerun the command to print the current
address.

Only the frontend reverse proxy is tunneled. FastAPI stays bound to
`127.0.0.1`; protected APIs still require Operator Unlock, scoped permissions,
CSRF protection, and the durable emergency control plane.

## Trusted home network

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-mobile-access.ps1
```

The script prints the private-network URL for the phone. Keep the laptop awake and
connected to the same trusted Wi-Fi. Only the Vite frontend listens on the LAN; the
FastAPI backend remains bound to `127.0.0.1` and is reached through the frontend
proxy. Operator Unlock is still required.

Plain HTTP is suitable for protected text control on a trusted home network, but
mobile browsers normally require HTTPS for microphone recognition and PWA install.
Do not use this mode on public or shared Wi-Fi.

## Secure remote and full voice use

Use a stable HTTPS hostname protected by a private VPN or Cloudflare Access. Do not
publish port 8000, disable the unlock gate, allow wildcard origins, or use a public
unauthenticated quick tunnel. This laptop has `cloudflared`, but no authenticated
Cloudflare origin certificate/tunnel is configured yet; a domain and Access policy
must be selected before that connection can be provisioned safely.
