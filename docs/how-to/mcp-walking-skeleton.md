# MCP walking skeleton

How-to. Prefer Compose: `make up` starts MCP on `http://127.0.0.1:8100/mcp` with the same Mongo as the API. Mint a PAT via Studio Settings or `POST /v1/orgs/current/pats`. For a host process instead: `python -m mymlfw.mcp` (stdio) or `--transport streamable-http --host 127.0.0.1`.

Authenticate with `Authorization: Bearer <pat>`. Mutating tools need `idempotency_key`. Mission loop: `list_projects` → `get_next_mission` → `report_mission_progress` → `complete_mission` (fencing token must match).

## Core tools

| Group | Tools |
| --- | --- |
| Missions | `list_projects`, `get_project_dashboard`, `get_next_mission`, `report_mission_progress`, `complete_mission` |
| Brain | `query_project_brain`, `advise_project` (citation firewall), `ingest_vault_brain`, `record_dead_end`, `append_vault_law` |
| Levers / Autopilot | `propose_lever_execution`, `get_next_autopilot_probe`, `complete_autopilot_rung` |
| Provenance | `register_external_asset`, `verify_project_licenses` |
| Contest-enforcer | `ntl_status` |
| CASMI / ranked | `dual_canary`, `diff_ranked_submissions`, `public_code_badge` |
| Kaggle ops | `kaggle_refresh`, `kaggle_submit_lifecycle` |
| Gaps | `report_mcp_gap`, `list_mcp_gaps` |
| Cloud | `connect_cloud_provider`, `quote_cloud_launch`, `launch_cloud_runner`, `stop_cloud_runner`, … |
| Human-only | `confirm_elicitation` (refuses PAT/agent actors) |

Prompts: `mission_loop`, `campaign_sync` (keep Studio updated during a Kaggle run), `cloud_launch`.

Agents running a full contest should follow [Keep a Studio project updated via MCP](agent-mcp-campaign-sync.md) so Overview tracks CV/public scores and assets automatically.

- Ranked / CASMI: [CASMI ranked canary](casmi-ranked-canary.md)
- Image / recon: [SiClink image / recon](siclink-image-recon.md)

OAuth 2.1 PKCE S256 helpers live in `mymlfw.mcp.oauth` behind `feature_flags.mcp_oauth`.
