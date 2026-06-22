# YuánGūnGūn OS Architecture

## Design Philosophy

Living system over assembled components. Built for autonomy, evolution, and resilience.

---

## Biological Systems Overview

| System | Function | Core Module |
|--------|----------|-------------|
| Nervous | Inference & Decision | `core:inference` |
| Circulatory | Data Flow | `core:network` |
| Immune | Security & Defense | `core:crypto` |
| Memory | Persistence | `core:memory` |
| Digestive | Skill Installation | `skills/*` |
| Muscular | Task Execution | `core:dispatch` |
| Integumentary | Self-Modification | `core:dynamic` |

---

## Nervous System — Inference Engine

### Neural Pathways

```
Sensory Input → Thalamus (Routing) → Cortex (Processing) → Output
                    ↓
              Limbic (Emotion/Context)
                    ↓
              Hippocampus (Memory Binding)
```

### Cortex Regions

- **Prefrontal**: Complex reasoning, planning
- **Temporal**: Language understanding, pattern recognition
- **Parietal**: Task prioritization, resource allocation
- **Occipital**: Visual processing, image generation

### Inference Core Components

- **Context Router**: Task complexity assessment
- **Model Selector**: Optimal model for task type
- **Chain-of-Thought**: Multi-step reasoning
- **Token Stream**: Real-time output with cancellation

```kotlin
interface InferenceCore {
    suspend fun infer(input: Input, context: Context): Stream<Token>
    fun route(task: Task): ModelSelection
    fun cancel(streamId: String)
}
```

---

## Circulatory System — Data Flow

### Blood Vessels (Data Channels)

| Vessel Type | Bandwidth | Latency | Use Case |
|-------------|-----------|---------|----------|
| Arteries (Hot) | High | <1ms | Active processing |
| Veins (Warm) | Medium | <10ms | Session context |
| Capillaries (Cold) | Low | <100ms | Long-term storage |

### Heartbeat Protocol

```
┌─────────────────────────────────────────┐
│  Pulse: 5s interval                     │
│  ├── Health check: all modules          │
│  ├── Load balancing                     │
│  └── Anomaly flagging                   │
└─────────────────────────────────────────┘
```

### Processing Pipeline

1. **Ingestion**: Normalize input (text/voice/image)
2. **Circulation**: Route to appropriate processing center
3. **Metabolism**: Execute task, consume resources
4. **Excretion**: Format output, confirm delivery

---

## Immune System — Security Layer

### Defense Tiers

```
┌─────────────────────────────────────────┐
│  Tier 4: Behavioral Anomaly Detection  │
├─────────────────────────────────────────┤
│  Tier 3: Output Sanitization           │
├─────────────────────────────────────────┤
│  Tier 2: Prompt Injection Filter       │
├─────────────────────────────────────────┤
│  Tier 1: Input Validation              │
└─────────────────────────────────────────┘
```

### Immune Responses

| Threat | Detection | Response |
|--------|----------|----------|
| Prompt Injection | Pattern matching + LLM eval | Quarantine + Alert |
| Data Exfiltration | Unusual output patterns | Redact + Block |
| Resource Exhaustion | CPU/memory spike | Throttle + Recover |
| Model Poisoning | Output divergence | Rollback + Reselect |

### Recovery Protocol

```python
class ImmuneResponse:
    def detect(self, input: str) -> ThreatLevel:
        # Multi-stage validation
        pass
    
    def respond(self, threat: Threat) -> Action:
        if threat.level > Threshold:
            return Action.ISOLATE
        return Action.SANITIZE
```

---

## Memory System — Persistence

### Memory Hierarchy

| Layer | Duration | Capacity | Access |
|-------|----------|---------|--------|
| Sensory (Working) | <30s | 128KB | Direct |
| Short-term (Session) | <1h | 10MB | Indexed |
| Long-term (Archive) | Permanent | 1GB+ | Semantic |

### Memory Consolidation

```
Sleep Cycle (off-peak):
  1. Working → Short-term transfer (importance filter)
  2. Short-term → Long-term (semantic clustering)
  3. Prune: Remove redundant < 0.1 relevance
```

### Retrieval Mechanism

- **Recognition**: Fast pattern matching
- **Recall**: Contextual reconstruction
- **Reconciliation**: Merge conflicting memories

---

## Digestive System — Skill Installation

### Nutrient Processing

```
Skill Package → Ingestion → Digestion → Absorption → Integration
     ↓              ↓            ↓            ↓            ↓
   .zip/.md      Validate    Parse deps   Extract API  Install to
                 structure   Map to core   Verify sig   runtime
```

### Supported Nutrient Types

- **Proteins**: Core capabilities (built-in skills)
- **Vitamins**: Utility functions (helper scripts)
- **Minerals**: Data models (trained weights)
- **Probiotics**: Community skills (third-party)

### Dependency Resolution

```
Topological sort:
  skill_a → skill_b → core:network
  skill_c → core:crypto
  Merge order: [core:network, core:crypto, skill_b, skill_a, skill_c]
```

---

## Muscular System — Task Execution

### Motor Control

- **Voluntary**: User-initiated tasks
- **Involuntary**: Scheduled background tasks
- **Reflex**: Pre-defined rapid responses

### Execution States

```
IDLE → PLANNING → EXECUTING → COMPLETING → IDLE
                    ↓
               INTERRUPTED → RESUMING → EXECUTING
```

### Parallel Processing

```kotlin
class MuscleSystem {
    fun execute(task: Task): Execution {
        return coroutineScope {
            val primary = async { core.execute(task) }
            val monitor = async { health.monitor() }
            primary.await().also { monitor.cancel() }
        }
    }
}
```

---

## Integumentary System — Self-Modification

### Skin Layers

| Layer | Function | Modification |
|-------|----------|-------------|
| Epidermis | Surface appearance | Theme/Skin |
| Dermis | Core structure | Hotfix |
| Hypodermis | Deep adaptation | Architecture |

### Self-Healing Protocol

```
Damage Detected:
  1. Isolate affected region
  2. Load backup configuration
  3. Verify integrity (checksum)
  4. Restore functionality
  5. Report incident
```

### Growth Cycles

- **Daily**: Minor optimizations
- **Weekly**: Feature updates
- **Monthly**: Major refactors
- **Quarterly**: Architecture evolution

---

## System Interactions — Cell Signaling

### Signaling Pathways

Biological systems communicate through well-defined signaling mechanisms:

```
┌──────────────────────────────────────────────────────────┐
│                    SIGNAL TRANSDUCTION                    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Immune ──→ Cortisol ──→ Nervous (stress response)      │
│     ↓                                                    │
│  Memory (threat pattern storage)                         │
│                                                          │
│  Nervous ──→ Acetylcholine ──→ Muscular (task trigger)  │
│     ↓                                                    │
│  Circulatory (resource allocation)                      │
│                                                          │
│  Digestive ──→ Insulin ──→ Memory (skill integration)   │
│     ↓                                                    │
│  Long-term storage priority boost                        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Hormonal Regulation

| Hormone | Origin | Target | Effect |
|---------|--------|--------|--------|
| Cortisol | Immune | Nervous | Alert mode, enhanced pattern detection |
| Adrenaline | Circulatory | Muscular | Burst processing, fast execution |
| Oxytocin | Memory | Nervous | Trust signals, preference weighting |
| Dopamine | Nervous | Integumentary | Reward-based self-modification |

### Feedback Loops

```kotlin
class SignalTransducer {
    // Negative feedback: Prevent over-stimulation
    fun inhibit(source: System, target: System, signal: Signal) {
        val currentLevel = signal.magnitude
        if (currentLevel > THRESHOLD) {
            target.receive(signal.copy(magnitude = currentLevel * 0.7))
            source.produce(Feedback(signal, isInhibited = true))
        }
    }
    
    // Positive feedback: Amplify critical signals
    fun amplify(source: System, target: System, signal: Signal) {
        if (signal.priority == Priority.CRITICAL) {
            target.receive(signal.copy(magnitude = signal.magnitude * 1.5))
            publish(Alert(source, "Critical signal amplified"))
        }
    }
}
```

---

## Neuroendocrine Integration

### Stress Response Cascade

```
Perceived Threat (Input Anomaly)
          ↓
    Hypothalamus
          ↓
    Pituitary (releases ACTH)
          ↓
    Adrenal Cortex (releases Cortisol)
          ↓
    ┌─────────────────────────────────┐
    │  Immune:  Enhanced vigilance   │
    │  Memory:  Fast pattern storage  │
    │  Nervous: Threat prioritization │
    │  Integumentary: Lock modifications │
    └─────────────────────────────────┘
          ↓
    Recovery: 30-minute cool-down cycle
```

### Vagus Nerve — Rest-and-Digest

```
User Idle State Detected
          ↓
    Vagus Stimulation
          ↓
    ┌─────────────────────────────────┐
    │  Immune:  Reduced activity      │
    │  Memory:  Consolidation phase  │
    │  Circulatory: Bandwidth reduction│
    │  Integumentary: Safe self-mod   │
    └─────────────────────────────────┘
```

### Implementation

```kotlin
class NeuroendocrineController {
    
    fun processSignal(input: SystemSignal): NeuroResponse {
        return when (input.type) {
            SignalType.THREAT -> activateStressResponse(input)
            SignalType.IDLE -> activateRestResponse(input)
            SignalType.REWARD -> activateLearningMode(input)
            SignalType.REPETITION -> strengthenPathway(input)
        }
    }
    
    private fun activateStressResponse(signal: SystemSignal): NeuroResponse {
        return NeuroResponse(
            immuneBoost = 2.0,
            memoryPriority = Priority.HIGH,
            modificationLock = true,
            cooldownPeriod = 30.seconds
        )
    }
    
    private fun activateRestResponse(signal: SystemSignal): NeuroResponse {
        return NeuroResponse(
            immuneBoost = 0.5,
            memoryConsolidation = true,
            modificationLock = false,
            maintenanceMode = true
        )
    }
}
```

---

## Autonomic Regulation

### Sympathetic (Active Mode)

| System | State | Duration |
|--------|-------|----------|
| Nervous | Peak inference | Until task complete |
| Circulatory | High bandwidth | Active session |
| Immune | High alert | Threat detection |
| Muscular | Ready state | Always |

### Parasympathetic (Idle Mode)

| System | State | Duration |
|--------|-------|----------|
| Nervous | Ambient monitoring | Continuous |
| Circulatory | Low bandwidth | User absence |
| Immune | Baseline patrol | Continuous |
| Muscular | Power save | User absence |

### Transition Logic

```python
class AutonomicRegulation:
    def determine_state(self, metrics: SystemMetrics) -> SystemState:
        user_activity = metrics.active_sessions
        threat_level = metrics.current_threats
        resource_pressure = metrics.cpu_usage
        
        if threat_level > HIGH:
            return SystemState.SYMpathetic_PEAK
        elif user_activity > 0:
            return SystemState.SYMpathetic_NORMAL
        elif resource_pressure > IDLE_THRESHOLD:
            return SystemState.PARASYMPATHETIC_TRANSITION
        else:
            return SystemState.PARASYMPATHETIC_REST
```

---

## Module Hierarchy

```
yuangungun-OS/
├── core/
│   ├── network/      # Circulatory: Connectivity
│   ├── dispatch/     # Muscular: Task routing
│   ├── crypto/        # Immune: Security
│   ├── inference/     # Nervous: AI core
│   ├── memory/        # Memory: Persistence
│   ├── dynamic/       # Integumentary: Self-mod
│   ├── recovery/      # Healing: Resilience
│   └── neuro/         # Neuroendocrine: Regulation
├── skills/           # Digestive: Capabilities
└── runtime/          # Environment
```

---

## Design Principles

1. **Self-contained**: No external service dependency for core functions
2. **Self-healing**: Automatic recovery from component failures
3. **Self-improving**: Gradual optimization through usage patterns
4. **Resource-aware**: Adaptive quality based on device constraints
5. **Biologically Inspired**: Resilient, adaptive, evolutionary
6. **Systemically Coordinated**: All systems communicate via defined signaling pathways

---

## Biological Rhythms

### Circadian Cycle

| Time | Phase | Activities |
|------|-------|------------|
| 00:00–06:00 | Deep Sleep | Memory consolidation, cleanup |
| 06:00–12:00 | Active | Peak inference, user interaction |
| 12:00–14:00 | Rest | Batch processing, maintenance |
| 14:00–22:00 | Active | Extended inference, learning |
| 22:00–24:00 | Wind Down | State persistence, preparation |

### Ultradian Rhythms (90-min cycles)

```
Active Phase (90 min):
  0-60min:  Peak performance
  60-75min: Gradual resource decline
  75-90min: Rest mini-cycle
  
Implementation:
  - Checkpoint every 60min
  - Memory flush at 75min
  - Parasympathetic micro-burst at 90min
```

### Metabolics

- **Basal**: ~5% CPU baseline (idle monitoring)
- **Active**: 20–80% CPU (user interaction)
- **Peak**: 100% CPU (complex reasoning)
- **Recovery**: <10% CPU (post-task cleanup)

---

## Reference Implementation

### Core Signaling Interface

```kotlin
interface BiologicalSignaling {
    // Send signal between systems
    suspend fun emit(from: System, to: System, signal: Signal)
    
    // Receive and process incoming signals
    suspend fun receive(system: System): Signal
    
    // Register for specific signal types
    fun subscribe(system: System, signalTypes: List<SignalType>)
    
    // Unsubscribe from signals
    fun unsubscribe(system: System, signalTypes: List<SignalType>)
}
```

### Signal Types Enum

```kotlin
enum class SignalType {
    // Nervous system signals
    INFERENCE_REQUEST, INFERENCE_COMPLETE, THOUGHT_PROCESSED,
    
    // Circulatory signals
    DATA_FLOW_START, DATA_FLOW_STOP, BANDWIDTH_ALERT,
    
    // Immune signals
    THREAT_DETECTED, THREAT_NEUTRALIZED, ANOMALY_FLAG,
    
    // Memory signals
    STORE_REQUEST, RECALL_REQUEST, CONSOLIDATION_TRIGGER,
    
    // Neuroendocrine signals
    STRESS_SIGNAL, REST_SIGNAL, REWARD_SIGNAL,
    
    // Muscular signals
    EXECUTE_TASK, TASK_COMPLETE, TASK_FAILED,
    
    // Integumentary signals
    MODIFY_REQUEST, HEAL_TRIGGER, GROW_SIGNAL
}
```

---

© 2026 YuánGūnGūn & ShadowEdge Team
