---
title: Circuit Breaker & Retry Routing Policy
tags: [pipeline, safety, routing, circuit-breaker]
tier: Archival
component: "app/graph/routing.py"
---

# Circuit Breaker & Retry Routing Policy

Prevents infinite retry loops in cyclic state machine execution.

## Policy
```python
if status == "compliant":
    return "persist_node"
elif retry_count <= max_compliance_retries:
    return "content_node"
else:
    return "manual_intervention_node"
```

Connected entities: [[LangGraph-Engine]], [[Compliance-Gate]], [[Manual-Intervention]].
