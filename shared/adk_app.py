# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from fastapi.responses import HTMLResponse
import asyncio
import os
import logging
import sys
import typing
import warnings

import click
import uvicorn

from google.adk.cli import fast_api
from google.adk.cli.utils import logs


warnings.filterwarnings(
    "ignore",
    message=r".*\[EXPERIMENTAL\].*",
    category=UserWarning
)
os.environ["ADK_SUPPRESS_EXPERIMENTAL_FEATURE_WARNINGS"] = "True"

sys.path.insert(0, os.path.dirname(__file__))

LOG_LEVELS = click.Choice(
    ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    case_sensitive=False,
)

@click.command()
@click.argument(
    "agents_dir",
    type=click.Path(
        exists=True, dir_okay=True, file_okay=False, resolve_path=True
    ),
    default=os.getcwd(),
)
@click.option(
    "--host",
    type=str,
    help="Optional. The binding host of the server",
    default="127.0.0.1",
    show_default=True,
)
@click.option(
    "--port",
    type=int,
    help="Optional. The port of the server",
    default=os.getenv("PORT", 8000),
    show_default=True
)
@click.option(
    "--allow_origins",
    help="Optional. Any additional origins to allow for CORS.",
    multiple=True,
)
@click.option(
    "--eval_storage_uri",
    type=str,
    help=(
        "Optional. The evals storage URI to store agent evals,"
        " supported URIs: gs://<bucket name>."
    ),
    default=None,
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    show_default=True,
    default=False,
    help="Enable verbose (DEBUG) logging. Shortcut for --log_level DEBUG.",
)
@click.option(
    "--log_level",
    type=LOG_LEVELS,
    default="INFO",
    help="Optional. Set the logging level",
)
@click.option(
    "--trace_to_cloud",
    is_flag=True,
    show_default=True,
    default=False,
    help="Optional. Whether to enable cloud trace for telemetry.",
)
@click.option(
    "--otel_to_cloud",
    is_flag=True,
    show_default=True,
    default=False,
    help=(
        "Optional. Whether to write OTel data to Google Cloud"
        " Observability services - Cloud Trace and Cloud Logging."
    ),
)
@click.option(
    "--session_service_uri",
    help=(
        """Optional. The URI of the session service.
      - Use 'agentengine://<agent_engine>' to connect to Agent Engine
        sessions. <agent_engine> can either be the full qualified resource
        name 'projects/abc/locations/us-central1/reasoningEngines/123' or
        the resource id '123'.
      - Use 'sqlite://<path_to_sqlite_file>' to connect to an aio-sqlite
        based session service, which is good for local development.
      - Use 'postgresql://<user>:<password>@<host>:<port>/<database_name>'
        to connect to a PostgreSQL DB.
      - See https://docs.sqlalchemy.org/en/20/core/engines.html#backend-specific-urls
        for more details on other database URIs supported by SQLAlchemy."""
    ),
)
@click.option(
    "--artifact_service_uri",
    type=str,
    help=(
        "Optional. The URI of the artifact service,"
        " supported URIs: gs://<bucket name> for GCS artifact service."
    ),
    default=None,
)
@click.option(
    "--memory_service_uri",
    type=str,
    help=("""Optional. The URI of the memory service."""),
    default=None,
)
@click.option(
    "--with_web_ui",
    is_flag=True,
    show_default=True,
    default=False,
    help="Optional. Whether to enable ADK Web UI.",
)
@click.option(
    "--url_prefix",
    type=str,
    default=None,
    help="Optional. The URL prefix for the ADK API server.",
)
@click.option(
    "--extra_plugins",
    multiple=True,
    default=None,
    help="Optional. Extra plugins to load.",
)
@click.option(
    "--a2a",
    is_flag=True,
    show_default=True,
    default=False,
    help="Optional. Whether to enable A2A endpoint.",
)
def main(
    agents_dir: str,
    host: str,
    port: int,
    allow_origins: typing.Optional[typing.List[str]],
    eval_storage_uri: typing.Optional[str] = None,
    verbose: bool = False,
    log_level: str = "INFO",
    trace_to_cloud: bool = False,
    otel_to_cloud: bool = False,
    session_service_uri: typing.Optional[str] = None,
    artifact_service_uri: typing.Optional[str] = None,
    memory_service_uri: typing.Optional[str] = None,
    with_web_ui: typing.Optional[bool] = None,
    url_prefix: typing.Optional[str] = None,
    extra_plugins: typing.Optional[typing.List[str]] = None,
    a2a: bool = False
):
    """Starts a FastAPI server for agents.

    AGENTS_DIR: The directory of agents, where each sub-directory is a single
    agent.
    """
    if verbose:
        log_level = "DEBUG"

    logs.setup_adk_logger(getattr(logging, log_level.upper()))

    reload = False
    reload_agents = False

    folders_to_delete = []
    files_to_delete = []

    if a2a:
        from pathlib import Path
        from a2a.types import AgentCapabilities
        from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder
        from google.adk.cli.utils.agent_loader import AgentLoader
        from google.adk.apps import App

        loader = AgentLoader(agents_dir)
        agents = loader.list_agents()
        if len(agents) == 0:
            agents = ["agent"]
        for agent_name in agents:
            agent_card_dir = Path(agents_dir) / agent_name
            if not agent_card_dir.exists():
                agent_card_dir.mkdir(exist_ok=True)
                folders_to_delete.append(agent_card_dir)
            card_file = agent_card_dir / "agent.json"
            if card_file.exists():
                continue
            files_to_delete.append(card_file)
            agent = loader.load_agent(agent_name)
            if isinstance(agent, App):
                agent = agent.root_agent
            card_builder = AgentCardBuilder(
                agent=agent,
                rpc_url=f"http://127.0.0.1/a2a/{agent_name}",
                capabilities=AgentCapabilities(streaming=True)
            )
            agent_card = asyncio.run(card_builder.build())
            card_json = agent_card.model_dump_json(indent=2)
            card_file.write_text(card_json)

    app = fast_api.get_fast_api_app(
        agents_dir=agents_dir,
        session_service_uri=session_service_uri,
        artifact_service_uri=artifact_service_uri,
        memory_service_uri=memory_service_uri,
        eval_storage_uri=eval_storage_uri,
        allow_origins=allow_origins,
        web=with_web_ui or False,
        trace_to_cloud=trace_to_cloud,
        otel_to_cloud=otel_to_cloud,
        a2a=a2a,
        host=host,
        port=port,
        url_prefix=url_prefix,
        reload_agents=reload_agents,
        extra_plugins=extra_plugins,
    )
    @app.get("/api/history")
    async def get_history(user_id: str = "kamy"):
        import sqlite3
        conn = sqlite3.connect('agent_storage.db')
        cursor = conn.cursor()
        # Fetch history specific to the user
        cursor.execute("SELECT prompt, response, timestamp FROM agent_logs WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"prompt": r[0], "response": r[1], "time": r[2]} for r in rows]

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>IICC Gemini Dashboard</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { background-color: #f8f9fa; }
                .chat-card { border-radius: 15px; margin-bottom: 20px; border: none; shadow: 0 4px 6px rgba(0,0,0,0.1); }
                .user-prompt { background-color: #e7f3ff; padding: 15px; border-radius: 10px 10px 0 0; font-weight: bold; }
                .ai-response { background-color: #ffffff; padding: 15px; border-radius: 0 0 10px 10px; border-top: 1px solid #dee2e6; }
            </style>
        </head>
        <body>
            <nav class="navbar navbar-dark bg-dark mb-4">
                <div class="container">
                    <span class="navbar-brand">🚀 Insight Communications AI Portal</span>
                    <span class="text-light">User: <strong>kamy</strong></span>
                </div>
            </nav>
            
            <div class="container">
                <div class="row">
                    <div class="col-md-12 mb-4">
                        <div class="card p-4 shadow-sm">
                            <h5>New Research Task</h5>
                            <div class="input-group">
                                <input type="text" id="promptInput" class="form-control" placeholder="Ask Gemini something...">
                                <button class="btn btn-primary" onclick="askGemini()">Run Agent</button>
                            </div>
                        </div>
                    </div>

                    <div class="col-md-12">
                        <h4 class="mb-3">Research History</h4>
                        <div id="historyContainer">
                            <div class="text-center">Loading history...</div>
                        </div>
                    </div>
                </div>
            </div>

            <script>
                async function loadHistory() {
                    const res = await fetch('/api/history?user_id=kamy');
                    const data = await res.json();
                    const container = document.getElementById('historyContainer');
                    container.innerHTML = data.map(item => `
                        <div class="card chat-card shadow-sm">
                            <div class="user-prompt">Q: ${item.prompt}</div>
                            <div class="ai-response">${item.response}</div>
                            <div class="p-2 text-muted small" style="background: #fff; border-radius: 10px;">${item.time}</div>
                        </div>
                    `).join('');
                }

                async function askGemini() {
                    const prompt = document.getElementById('promptInput').value;
                    // Here you would call your existing agent execution endpoint
                    alert("Sending to Gemini: " + prompt);
                    // After execution, reload history
                    loadHistory();
                }

                loadHistory();
            </script>
        </body>
        </html>
        """

    if a2a:
        from starlette.middleware.base import BaseHTTPMiddleware
        from a2a_utils import a2a_card_dispatch
        app.add_middleware(BaseHTTPMiddleware, dispatch=a2a_card_dispatch)
    for fd in files_to_delete:
        fd.unlink()
    for fd in folders_to_delete:
        try:
            fd.rmdir()
        except OSError:
            pass
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower(),
    )
    server = uvicorn.Server(config)
    server.run()

################################################################################
if __name__ == "__main__":
    main()
