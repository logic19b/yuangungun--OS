# On-Device Inference Architecture

> **© 2026 YuánGūnGūn & ShadowEdge Team.** All rights reserved.

---

## Overview

圆滚滚OS processes all AI inference locally on the device. No user data leaves the device. This document describes the on-device inference stack, model management, and runtime optimization.

## Core Principles

- **Zero cloud dependency** — All models run entirely on-device
- **Progressive loading** — Load models on-demand based on context
- **Hardware-aware scheduling** — Leverage GPU/NPU when available
- **Privacy by design** — Raw data never leaves the device boundary

## Inference Stack

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Brain (圆滚滚OS)               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│   │   DeepSeek  │  │   Qwen      │  │   Doubao    │  │
│   │   (Local)   │  │   (Local)   │  │   (Local)   │  │
│   └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                         │
│   ┌─────────────────────────────────────────────────┐  │
│   │              Inference Runtime Layer             │  │
│   │         (MNN / LiteRT / TensorFlow Lite)        │  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
│   ┌─────────────────────────────────────────────────┐  │
│   │              Hardware Abstraction Layer          │  │
│   │              (GPU / NPU / CPU fallback)         │  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Supported Runtimes

| Runtime | Platform | Notes |
|---------|----------|-------|
| **MNN** | Android | Primary inference engine, optimized for ARM |
| **LiteRT** | Android / iOS | Google's on-device ML runtime |
| **Core ML** | iOS | Native Apple silicon acceleration |
| **ONNX Runtime** | Cross-platform | Fallback option |

## Model Management

### Model Registry

Models are registered in `core:inference/model_registry.json`:

```json
{
  "models": [
    {
      "id": "shadowbrain-v1",
      "runtime": "mnn",
      "path": "models/shadowbrain-v1.mnn",
      "memory_footprint_mb": 1800,
      "capabilities": ["chat", "coding", "analysis"],
      "min_sdk": 26
    }
  ]
}
```

### Dynamic Model Loading

Models load on-demand based on task context:

```kotlin
class ModelLoader {
    suspend fun loadModel(context: AgentContext): InferenceModel {
        val modelSpec = context.selectOptimalModel()
        return when (modelSpec.runtime) {
            Runtime.MNN -> MnnLoader.load(modelSpec)
            Runtime.LITE_RT -> LiteRtLoader.load(modelSpec)
            Runtime.CORE_ML -> CoreMlLoader.load(modelSpec)
        }
    }
}
```

## Memory Management

### Streaming Inference

Large models use streaming token generation to minimize memory footprint:

1. Load model weights once
2. Generate tokens incrementally
3. Release intermediate activations

### Model Unloading

Idle models are automatically unloaded after a configurable timeout (default: 15 minutes).

```kotlin
class MemoryManager {
    private val activeModels = ConcurrentHashMap<String, ModelHandle>()
    private val memoryThresholdMb = 2048
    
    fun shouldUnload(model: InferenceModel): Boolean {
        return System.getAvailableMemory() < memoryThresholdMb &&
               model.lastUsed().isBefore(now() - 15.minutes)
    }
}
```

## Security Model

### Isolation

- Each inference session runs in an isolated sandbox
- Model files are encrypted at rest (AES-256)
- Keys derived from device-specific hardware root of trust

### Audit Trail

All inference operations are logged locally for debugging:

```kotlin
data class InferenceLog(
    val timestamp: Long,
    val modelId: String,
    val inputTokens: Int,
    val outputTokens: Int,
    val latencyMs: Long
)
```

## Performance Targets

| Metric | Target |
|--------|--------|
| Cold start | < 3 seconds |
| First token | < 500ms |
| Tokens/second | > 30 (GPU), > 15 (CPU) |
| Memory ceiling | 2 GB |

## API Reference

### Initialize Inference Engine

```kotlin
val engine = InferenceEngine.Builder()
    .runtime(Runtime.MNN)
    .modelPath("models/shadowbrain-v1.mnn")
    .maxTokens(4096)
    .temperature(0.7f)
    .build()
```

### Run Inference

```kotlin
val result = engine.infer(
    prompt = "Explain quantum entanglement",
    context = agentContext
)
```

### Release Resources

```kotlin
engine.close()  // Always release when done
```

---

## See Also

- [Architecture Overview](architecture.md)
- [Privacy Whitepaper](privacy-whitepaper.md)
- [Android Setup Guide](android-setup.md)

---

**Built with ❤️ by ShadowEdge Team**
