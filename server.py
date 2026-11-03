import asyncio
import hmac
import os
from pathlib import Path
import subprocess
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

ROOT = Path('/projects').resolve()
TOKEN = os.environ['CAD_MCP_TOKEN']
PUBLIC_HOST = os.environ.get('CAD_MCP_PUBLIC_HOST', '').strip().lower()
hosts = ['127.0.0.1:8767', 'localhost:8767', 'cad-pcb-mcp:8767']
if PUBLIC_HOST:
    hosts.extend([PUBLIC_HOST, PUBLIC_HOST + ':443'])
mcp = FastMCP('cad-pcb-mcp', stateless_http=True, json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
        allowed_hosts=hosts, allowed_origins=[]))

def safe_file(name: str, suffixes: tuple[str, ...]) -> Path:
    if not name or name.startswith(('/', '\\')) or '\\' in name or ':' in name:
        raise ValueError('Use a relative Linux project path')
    p = (ROOT / name).resolve()
    if not p.is_relative_to(ROOT) or p.suffix.lower() not in suffixes:
        raise ValueError('Disallowed path or extension')
    if not p.is_file() or p.stat().st_size > 5_000_000:
        raise ValueError('File missing or exceeds 5 MB')
    return p

async def run(*args: str, timeout: int = 40) -> str:
    def blocking():
        try:
            p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, timeout=timeout, cwd=ROOT,
                text=True, errors='replace', env={'PATH': os.getenv('PATH', ''),
                'HOME': '/home/engineer', 'QT_QPA_PLATFORM': 'offscreen'})
            return f'exit_code={p.returncode}\nstdout:\n{p.stdout[:7000]}\nstderr:\n{p.stderr[:3000]}'
        except subprocess.TimeoutExpired:
            return 'ERROR: Tool timed out'
        except Exception as e:
            return f'ERROR: {type(e).__name__}'
    return await asyncio.to_thread(blocking)

@mcp.tool()
async def cad_tool_versions() -> str:
    """Show installed KiCad CLI, OpenSCAD and ngspice versions."""
    responses = []
    for command in [('kicad-cli', 'version'), ('openscad', '--version'), ('ngspice', '--version')]:
        responses.append(command[0] + ':\n' + await run(*command, timeout=10))
    return '\n'.join(responses)

@mcp.tool()
async def kicad_check_pcb(path: str) -> str:
    """Perform PCB design-rule checks on an existing project .kicad_pcb file."""
    return await run('kicad-cli', 'pcb', 'drc', '--exit-code-violations', str(safe_file(path, ('.kicad_pcb',))), timeout=60)

@mcp.tool()
async def kicad_check_schematic(path: str) -> str:
    """Perform schematic electrical-rule checks on an existing .kicad_sch file."""
    return await run('kicad-cli', 'sch', 'erc', '--exit-code-violations', str(safe_file(path, ('.kicad_sch',))), timeout=60)

@mcp.tool()
async def openscad_render_stl(path: str) -> str:
    """Render an existing OpenSCAD project file to STL within the project workspace."""
    source = safe_file(path, ('.scad',))
    destination = source.with_suffix('.stl')
    if destination.is_symlink():
        raise ValueError('Symlink output forbidden')
    result = await run('openscad', '-o', str(destination), str(source), timeout=60)
    return result + ('\noutput=' + str(destination.relative_to(ROOT)) if destination.is_file() else '')

@mcp.tool()
async def ngspice_batch(path: str) -> str:
    """Run ngspice batch simulation against an existing .cir or .sp netlist."""
    return await run('ngspice', '-b', str(safe_file(path, ('.cir', '.sp'))), timeout=40)

class BearerAuth:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            headers = dict(scope.get('headers', []))
            supplied = headers.get(b'authorization', b'').decode('utf-8', 'replace')
            if not hmac.compare_digest(supplied, 'Bearer ' + TOKEN):
                await send({'type': 'http.response.start', 'status': 401,
                    'headers': [(b'content-type', b'text/plain')]})
                await send({'type': 'http.response.body', 'body': b'Unauthorized'})
                return
        await self.app(scope, receive, send)

if __name__ == '__main__':
    uvicorn.run(BearerAuth(mcp.streamable_http_app()), host='0.0.0.0', port=8767)
