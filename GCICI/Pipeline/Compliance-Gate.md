---
title: Compliance Gate Node
tags: [pipeline, agent, compliance, rubric, guardrail]
tier: Archival
component: "app/graph/nodes/compliance_gate.py"
---

# Compliance Gate Node

The statutory gatekeeper evaluating every marketing draft against [[Universal-Rubric]].

## Operational Policy
- Grounded in `compliance_rubric.md` read from disk on every invocation.
- Increments `retry_count`.
- Proposes minimal redlines replacing prohibited superlatives.
- Routes compliant drafts to persistent queue; routes failed drafts to [[Content-Agent]] or [[Circuit-Breaker]].

Connected entities: [[LangGraph-Engine]], [[Universal-Rubric]], [[Circuit-Breaker]].
