# Architecture

## The Living AI Layer

YuánGūnGūn OS is built on a radical idea: **AI should be more like an organism than a tool.**

Traditional AI systems are stateless function calls. They wake on demand, sleep on disconnect, and forget everything overnight. We asked: what if AI had biological systems — not as metaphors, but as real architectural patterns?

---

## The 10 Biological Systems

### Vital Systems (Keep It Alive)

| System | Responsibility | Key Implementation |
|--------|---------------|-------------------|
| 🫀 **Cardiac** | Temporal processing rhythm | Pulsed inference scheduling, heartbeat-driven task queue |
| ⚡ **Metabolic** | Energy-aware processing | Battery/CPU monitoring, dynamic inference model selection |
| 🌙 **Circadian** | Sleep-wake cycles | Scheduled consolidation, idle-time optimization |
| ⚖️ **Homeostatic** | Self-regulation | Auto-balancing load, memory, and response quality |

### Defense Systems (Keep It Safe)

| System | Responsibility | Key Implementation |
|--------|---------------|-------------------|
| 🛡️ **Immune** | Injection defense | Multi-layer prompt injection detection + isolation + recovery |
| ⚡ **Instinctive** | Pre-conscious threat detection | Anomaly detection, rapid response without full inference |
| 💪 **Stress** | Adaptive load management | Priority queuing, graceful degradation under pressure |

### Cognition Systems (Keep It Smart)

| System | Responsibility | Key Implementation |
|--------|---------------|-------------------|
| 🧠 **Subconscious** | Background pattern memory | Offline pattern recognition, associative recall |
| 😴 **Sleep** | Memory consolidation | Periodic optimization, pruning, compression |
| 🍂 **Forgetting** | Natural memory decay | Time-weighted decay, access reinforcement |

---

## Why Biological Systems?

Each system solves a real engineering problem:

| Problem | Biological Solution |
|---------|-------------------|
| On-device AI has limited compute | Metabolic + Cardiac manage processing budget |
| On-device AI is vulnerable | Immune + Instinctive defend against attacks |
| On-device AI has limited storage | Forgetting + Sleep manage memory lifecycle |
| On-device AI needs offline operation | All systems are self-contained, no cloud dependency |
| AI needs to adapt to user patterns | Circadian + Subconscious enable background learning |

---

## Tech Stack

```
┌─────────────────────────────────────────┐
│           Presentation Layer             │
│   Jetpack Compose (Android) / SwiftUI   │
├─────────────────────────────────────────┤
│           Business Logic                 │
│   Kotlin / KMP Shared / Swift           │
│   Hilt DI                                │
├─────────────────────────────────────────┤
│           Biological Systems             │
│   Cardiac / Immune / Metabolic / ...    │
├─────────────────────────────────────────┤
│           Inference Layer                │
│   MNN (On-device LLM) + LiteRT          │
│   5-tier fallback chain                  │
├─────────────────────────────────────────┤
│           Security Layer                 │
│   Certificate Pinning + Encryption      │
└─────────────────────────────────────────┘
```

---

## The 5-Tier Inference Fallback

1. **Local LLM** (MNN) — Fast, private, always available
2. **Rule Engine** — Pattern matching for common queries
3. **Lightweight Cloud** — Small model via API (minimal data)
4. **Heavy Cloud** — Large model via API (better quality)
5. **Graceful Degradation** — "I can't answer this right now"

---

© 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
