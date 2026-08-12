# Access control

Declare roles that should receive Agent-object usage:

```yaml
access:
  usage_roles:
    - ORDERS_AGENT_USER
  monitor_roles:
    - ORDERS_AGENT_MONITOR
```

Preview and apply:

```bash
dbt run-operation cortex_agent__grant_usage \
  --args '{"agent_name":"orders_assistant","dry_run":true}'

dbt run-operation cortex_agent__grant_usage --target sandbox \
  --args '{"agent_name":"orders_assistant","dry_run":false}'
```

The apply path is sandbox-guarded and idempotent. It grants `USAGE ON AGENT` to
`usage_roles` and `MONITOR ON AGENT` to `monitor_roles`. Evaluation roles normally
need both privileges, so list the evaluation role under both keys.
Database/schema, warehouse, semantic-view, search-service, procedure, stage, and
Cortex privileges remain consumer responsibilities.
