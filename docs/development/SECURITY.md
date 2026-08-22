
## M1 Security Posture

- Read-only market API; no order endpoints exist.
- Alpaca credentials read from env only; never logged; paper/IEX feed.
- No agent holds execution permission in M1; PLACE_ORDER remains gated to
  runtime authorization events (execution milestone).
- Fixture data labeled provider="fixture"; never rendered as live.
