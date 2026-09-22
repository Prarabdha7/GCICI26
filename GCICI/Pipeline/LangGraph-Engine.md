---
title: LangGraph Orchestration & Cyclic State Machine
tags: [pipeline, langgraph, architecture, state-machine]
tier: Archival
component: "app/graph/graph.py"
---

# LangGraph Orchestration & Cyclic State Machine

The core intelligence coordinating the multi-agent content generation workflow.

```
START ──> Memory Retrieval ──> Market Research ──> Content Agent ──> Localization
                                                        ▲                  │
                                                        │ (retry <= 3)     ▼
                 Persist (Pending) <── Compliant <── Compliance Gate <── Media Assembly
                                            │
                                            ▼ (retry > 3)
                                  Manual Intervention
```

## Cyclic vs Linear Pipeline
Unlike naive prompt chains, the content pipeline incorporates an active feedback loop. When [[Compliance-Gate]] discovers regulatory violations, it routes execution back to [[Content-Agent]] with specific rubric violations attached.

## Circuit Breaker
When `retry_count > 3`, the [[Circuit-Breaker]] fires, terminating the loop and diverting the generation to [[Manual-Intervention]].

Connected Pipeline Nodes:
- [[Memory-Retrieval-Agent]]
- [[Market-Research-Agent]]
- [[Content-Agent]]
- [[Localization-Agent]]
- [[Compliance-Gate]]
- [[Circuit-Breaker]]
- [[Publisher-Worker]]
