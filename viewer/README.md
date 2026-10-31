# Benchmark viewer

A small local web app for browsing the benchmark's episodes and saved runs.

- **Runs** lists every run file under `runs/` and `reports/` (schema `faraday-industrial-run/*`). A run page shows the summary metrics and per-episode, per-family and per-capability results. An episode page shows the prompt, the agent's final answer, the score breakdown, criteria, violations, and a timeline that places scheduled events between the tool calls.
- **Examples** lists every `data/<set>/tasks.json`. An episode page shows the prompt, setup, workflow stages, scheduled events, and the saved runs that include that episode version.

Task files don't store scheduled events, and run files store only the IDs of the events that fired. So the viewer runs `scripts/scenario_events.py` when a page needs events:

- For an example, it generates the events from the scenario code and the task's seed.
- For a run episode, it replays the run's tool calls through the benchmark to find when each event fired. That includes events the agent's own calls scheduled, such as approval decisions. If the current code doesn't reproduce the run exactly, the page says so.

Results are cached until the task file, the run file, or the benchmark's Python source changes.

## Requirements

- Node.js 22.17 or newer.
- Python 3.11 or newer to generate and replay events. If [uv](https://docs.astral.sh/uv/) is on your `PATH`, the viewer runs `uv run --no-project --python '>=3.11' python`. Otherwise it runs `python3`. The benchmark has no third-party dependencies, so no virtual environment is needed.

## Run it

```sh
cd viewer
npm install
npm run dev
```

Then open <http://localhost:5173>. The viewer reads files on every request, so a new run file shows up when you reload. To save a run, install the benchmark as the main README describes, then run this from the repository root:

```sh
faraday-bench run --agent oracle --output runs/oracle.json
```

### Settings

| Variable         | Default                         | Purpose                                                 |
| ---------------- | ------------------------------- | ------------------------------------------------------- |
| `FARADAY_REPO`   | The directory above `viewer/`   | Benchmark checkout to read tasks, runs and code from.   |
| `FARADAY_PYTHON` | `uv run …` or `python3`, above  | Command that runs the helper, such as `python3.12`.     |

For example: `FARADAY_PYTHON=python3.12 npm run dev`.

## Keep it local

The server reads files from the repository and starts Python processes on request, and it has no authentication. `npm run dev` listens on localhost only. If you run the production build, bind it to localhost too, because the Node adapter listens on all interfaces by default:

```sh
npm run build
HOST=127.0.0.1 node build
```

Run `node build` from `viewer/`, since the server finds the repository relative to its working directory. It serves on port 3000 unless you set `PORT`.

## Development

```sh
npm run check   # Svelte and TypeScript diagnostics
npm test        # Unit tests; the helper tests run Python, so they need Python 3.11+
```

- `src/lib/server/` finds run and task files and runs the Python helper.
- `src/lib/timeline.ts` places replayed events between a run's tool calls.
- `src/routes/` holds the pages. UI primitives in `src/lib/components/ui/` come from [shadcn-svelte](https://www.shadcn-svelte.com/).
