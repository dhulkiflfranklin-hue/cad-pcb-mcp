# CAD/PCB MCP for TrueForge

Authenticated, Docker-hosted MCP tools: KiCad PCB DRC, schematic ERC, OpenSCAD STL rendering, ngspice batch simulation, and version discovery.

This starter does **not** yet include FreeCAD, GUI sessions, or KiCad manufacturing exports.

## Install on Windows

1. Install Docker Desktop with Linux containers and Git.
2. Download/extract this project, or copy these files into your public `cad-pcb-mcp` repository.
3. In PowerShell within the project folder:

```powershell
Copy-Item .env.example .env
$b = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($b)
$rng.Dispose()
$token = [Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_')
"CAD_MCP_TOKEN=$token`nCAD_MCP_PUBLIC_HOST=" | Set-Content .env
New-Item -ItemType Directory -Force projects | Out-Null
docker compose up -d --build
```

Do not print or share the token, and never commit `.env` or proprietary project files. Depending on host architecture and available package repositories, KiCad/OpenSCAD packages may need adjustments. Building the image can use considerable memory and disk.

4. Check `docker compose ps` and `docker compose logs --tail 30` (review logs for sensitive information before sharing).
5. Unauthenticated `curl.exe -i http://127.0.0.1:8767/mcp` should return **401 Unauthorized**.
6. Put sample engineering input files in `projects/`; they become `/projects` inside the container.

## Secure TrueForge connector

TrueForge blocks localhost MCP URLs. Set up a protected HTTPS ingress, preferably a named Cloudflare Tunnel with access controls in addition to the required MCP bearer token. The URL's hostname must be set in `.env` as `CAD_MCP_PUBLIC_HOST=your.host.example`, with no scheme or path; restart Docker Compose afterward. The ingress must preserve `Authorization: Bearer` headers. Quick Tunnels are unsuitable for dependable production use.

In TrueForge > Settings > Connectors > Add MCP Server:
- Name: `cad-pcb-mcp`
- URL: `https://YOUR_HOST/mcp`
- Auth: API Key/Bearer, using your `.env` token; leave optional header name empty.

The tools intentionally do not expose arbitrary shell execution or source-code upload. Input files must be placed into the project's dedicated workspace. Tools can write reports/STLs within the mounted workspace, so use backups and restrict who can invoke them. Untrusted CAD inputs may consume resources despite container restrictions. KiCad command behavior varies by version; confirm CLI flags before relying on checks.
