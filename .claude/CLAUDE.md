# cv-harvester - Agentic CV Intelligence Tool

> A Claude Code slash command that deploys four parallel sub-agents to mine your
> local projects, GitHub history, and job applications - producing per-project
> CV entries tailored to the roles you are actually applying for.

---

## Your setup

| What | Where |
|---|---|
| Code projects | `C:\Code\CV_crawl\` |
| Job applications | `C:\Users\brans\OneDrive - University of Leeds\GraduateJobHunting\` |
| GitHub | github.com/Brandnewson |
| Claude Code command | `.claude\commands\cv-harvest.md` |
| Output file | `C:\Code\CV_crawl\.cv-harvest-output.md` |

---

## Architecture

```
User types: /cv-harvest
                |
                v
     +----------------------+
     |   ORCHESTRATOR       |
     |   Step 0: list Code\ |
     +--+-------------------+
        |  fires all four simultaneously via Task()
        |
   +----+------+-------------+--------------+
   v           v             v              v
Code        GitHub       Job Target     Git History
Analyst     Analyst       Analyst        Analyst
   |           |             |              |
   +-----------+-------------+--------------+
                       |
               structured XML
                       |
                       v
              +-----------------+
              |   CV WRITER     |
              |   sub-agent     |
              +--------+--------+
                       |
           .cv-harvest-output.md
```

### Agentic patterns demonstrated

| Pattern | Where |
|---|---|
| **Orchestrator/sub-agent decomposition** | Orchestrator -> 4 analysts -> 1 writer |
| **Parallel Task execution** | All 4 analysts fire simultaneously |
| **Structured XML inter-agent protocol** | Every agent speaks typed XML schemas |
| **Tool-augmented agents** | Agents run PowerShell, curl, Python as tools |
| **Job-aware synthesis** | CV Writer seeded with keyword targets from your applications |
| **Confidence-tagged output** | Bullets carry evidence confidence levels |
| **Multi-source triangulation** | Code + GitHub + git log = corroborated evidence |

---

## Setup steps

### 1. Install Claude Code

Requires Node.js 18+. Check your version:
```powershell
node --version
```
If below 18, download from nodejs.org.

Install Claude Code:
```powershell
npm install -g @anthropic-ai/claude-code
```

### 2. Copy the .claude folder into your Code directory

```powershell
Copy-Item -Recurse "path\to\cv-harvester\.claude" "C:\Code\CV_crawl\.claude"
```

Your Code folder should now look like:
```
C:\Code\CV_crawl\
+-- .claude\
|   +-- commands\
|   |   +-- cv-harvest.md
|   +-- mcp.json
+-- project-1\
+-- project-2\
+-- ...
```

### 3. (Optional but recommended) Add MCP servers

Skip the `claude mcp add` CLI - just paste this file directly:

**Create `C:\Code\CV_crawl\.claude\mcp.json`** with this content:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "C:\\Code\\CV_crawl"]
    },
    "git": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-git", "C:\\Code\\CV_crawl"]
    }
  }
}
```

The `mcp.json` file is already included in the `.claude` folder you downloaded - just make sure it lands at `C:\Code\CV_crawl\.claude\mcp.json`.

### 4. Log in and run

```powershell
claude login
cd "C:\Code\CV_crawl"
claude
> /cv-harvest
```

Expect 2-5 minutes. Output saved to `.cv-harvest-output.md`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `claude: command not found` | Check PATH after npm install |
| `pypdf` or `mammoth` errors | Run `pip install pypdf mammoth --break-system-packages` |
| GitHub rate limit | Set `GITHUB_TOKEN` env var for 5000 req/hr |
| OneDrive path errors | Verify exact path with `ls "C:\Users\brans\OneDrive - University of Leeds"` |
| No git output | Ensure project folders have `.git` directories |
