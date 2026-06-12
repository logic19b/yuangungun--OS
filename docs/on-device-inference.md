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

## Quantization Support

Models are quantized to reduce memory footprint and improve inference speed.

### Quantization Levels

| Level | Precision | Memory Reduction | Quality Loss |
|-------|-----------|------------------|--------------|
| **FP16** | 16-bit float | 50% | Minimal |
| **INT8** | 8-bit integer | 75% | Low |
| **INT4** | 4-bit integer | 87.5% | Moderate |
| **Mixed** | Dynamic | 60-80% | Low |

### Quantized Model Loading

```kotlin
class QuantizedModelLoader {
    suspend fun loadQuantized(
        modelSpec: ModelSpec,
        precision: QuantPrecision = QuantPrecision.INT8
    ): InferenceModel {
        val quantizedPath = resolveQuantizedPath(modelSpec, precision)
        return runtime.load(quantizedPath)
    }
}
```

## Speculative Decoding

Accelerate inference using a small draft model to predict tokens in parallel.

### Architecture

```
┌──────────────────┐
│   Prompt Input   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  Draft Model     │────▶│  Verify Tokens   │
│  (4B params)     │     │  (speculative)   │
└──────────────────┘     └────────┬─────────┘
                                  │
         ┌────────────────────────┘
         ▼
┌──────────────────┐
│  Target Model    │
│  (7B+ params)    │──▶ Final Output
└──────────────────┘
```

### Speedup Metrics

- **2-3x faster** token generation on multi-core devices
- **Maintains quality** — identical outputs to autoregressive decoding
- **Energy efficient** — fewer compute cycles overall

```kotlin
class SpeculativeDecoder(
    private val draftModel: InferenceModel,
    private val targetModel: InferenceModel,
    private val maxDraftTokens: Int = 4
) {
    suspend fun decode(input: String): TokenStream {
        val drafts = draftModel.generate(input, maxDraftTokens)
        return targetModel.verify(drafts)
    }
}
```

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

### Version Management

```kotlin
data class ModelVersion(
    val id: String,
    val version: String,
    val checksum: String,
    val quantization: QuantPrecision,
    val downloadUrl: String? = null  // For OTA updates
)
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

### Memory Pressure Response

```kotlin
sealed class MemoryPressure {
    object Low : MemoryPressure()      // Normal operation
    object Medium : MemoryPressure()    // Pause background tasks
    object High : MemoryPressure()      // Unload idle models
    object Critical : MemoryPressure()  // Emergency unloading
}
```

## Local RAG Integration

On-device retrieval-augmented generation for context-aware inference.

### Vector Storage

```kotlin
class LocalVectorStore(
    private val dimension: Int = 384,
    private val maxEntries: Int = 10000
) {
    suspend fun add(embedding: FloatArray, metadata: Map<String, String>)
    suspend fun search(query: FloatArray, topK: Int): List<SearchResult>
    suspend fun delete(id: String)
}
```

### RAG Pipeline

```
Query → Embed → Search → Context → LLM → Response
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
