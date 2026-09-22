---
title: Memory Retrieval Agent
tags: [pipeline, agent, memory, feedback]
tier: RAM / Recall
component: "app/graph/nodes/memory_retrieval.py"
---

# Memory Retrieval Agent

Fetches the last 5 human edits and rejections from [[Tier-2-Mem0-Buffer]] before [[Content-Agent]] drafts copy.

## Key Attributes
- Runs exactly once at pipeline initiation.
- Grounds agent generation in historical operational feedback.
- Prevents repeating previous marketing errors.

Connected entities: [[LangGraph-Engine]], [[Tier-2-Mem0-Buffer]], [[Content-Agent]].
