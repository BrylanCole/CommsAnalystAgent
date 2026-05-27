# Comms Analyst Team Portal

Use this GitHub-native portal to request and track reports.

- [Submit a new report request](../../issues/new?template=report-request.yml)
- [View report workflow runs](../../actions/workflows/run-comms-analyst-from-issue.yml)
- [View recent successful runs](../../actions/workflows/run-comms-analyst-from-issue.yml?query=is%3Asuccess)

## How it works

1. Create a **Report Request** issue with a plain-English monitoring prompt.
2. GitHub Actions runs the agent and uploads `report.md` and `report.json` as artifacts.
3. The workflow posts a completion/failure comment back on the issue with a run link.
4. To re-run a request, add the `run-report` label to the issue.

## Access control

Use a private repository and team permissions so only approved members can submit requests and view artifacts.
