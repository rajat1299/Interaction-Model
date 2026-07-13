# Interaction Model

Behavioral replication of a text interaction model (held facts, marks, live
lookups, recurring timers) fine-tuned on `Qwen/Qwen3.6-35B-A3B` (thinking
disabled). Event-sourced runtime, nine-action policy, SFT + DPO.

Full plan: [docs/build-plan.md](docs/build-plan.md).

## WP13 dry run

The prompted policy is configured for OpenAI `gpt-5.6-terra` with high reasoning. Before any
live request, validate the local key and print expected/conservative costs:

```bash
uv run python scripts/wp13_dry_run.py
```

The command never calls OpenAI and never prints the key. A live browser run needs the API and Vite
processes in separate terminals:

```bash
uv run uvicorn im.entrypoint:app --host 127.0.0.1 --port 8000
cd client && npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/`; Vite proxies the session HTTP and WebSocket routes to the API. The
first recorded live run is in
[`probes/results/e2e/2026-07-12-terra-high.md`](probes/results/e2e/2026-07-12-terra-high.md).

## Layout

- `docs/` — canonical build plan and specs.

Source layout is defined as Phase 0a lands; the plan deliberately fixes no
structure ahead of the work.
