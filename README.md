# orchestrate-devin-sessions

A small script that creates a Devin session via the v3 API, waits for it to
finish and return structured output, then **terminates** the session so it
stops running.

## Why terminate?

Devin orgs have a limit on how many sessions can run **in parallel**. Once a
session's work is done (PR opened, structured output received), we want it to
stop running as soon as possible so that slot frees up for other work.

## What the terminate endpoint does

```
DELETE /v3/organizations/{org_id}/sessions/{devin_id}?archive=false
```

- **Stops the session immediately.** Its status moves to `exit`, so it no
  longer counts against your parallel-session limit. This is the fastest,
  most deterministic way to free a slot.
- **Preserves history.** It does **not** delete the session. The session
  record, its messages, the pull request it opened, and the structured output
  all remain and stay queryable via `GET .../sessions/{devin_id}`.
- **Is one-way.** A terminated session **cannot be resumed**. Use this only
  when the work is finished.
- **Optional `archive` flag.** Pass `archive=true` to also archive the session
  (hide it from the default session list) in the same call. Defaults to
  `false`.

### Terminate vs. sleep vs. archive

| Action | Stops running | History preserved | Resumable | Endpoint |
| --- | --- | --- | --- | --- |
| **Terminate** | Yes, immediately | Yes | No | `DELETE .../sessions/{id}` |
| **Sleep** (suspend) | Eventually | Yes | Yes | only via a `"sleep"` chat message |
| **Archive** | Yes | Yes (archived) | No | `POST .../sessions/{id}/archive` |

There is no dedicated "suspend"/"sleep" API endpoint — suspending can only be
triggered by sending the session a `"sleep"` message. Since we don't need to
resume finished work, terminate is the cleanest fit.

## Usage

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -u run_session/run_session.py
```

The script reads `DEVIN_API_KEY` from a `.env` file.
