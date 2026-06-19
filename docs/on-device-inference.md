# On-Device Inference Architecture

> **© 2026 YuánGūnGūn & ShadowEdge Team.** All rights reserved.

---

## Overview

圆滚滚OS processes all AI inference locally on the device. No user data leaves the device without explicit consent. This document describes the on-device inference stack, model management, and runtime optimization.

## Core Principles

- **Zero cloud dependency** — All models run entirely on-device by default
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
    object Medium : MemoryPressure()   // Pause background tasks
    object High : MemoryPressure()     // Unload idle models
    object Critical : MemoryPressure() // Emergency unloading
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

## Streaming Tool Calling

Execute tools mid-generation without interrupting token stream.

### Architecture

```
┌─────────────────────────────────────────────┐
│         Token Stream (real-time)             │
├─────────────────────────────────────────────┤
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐     │
│  │Token │→ │Token │→ │ <tool_call> │→ │Token │     │
│  │  A   │  │  B   │  │  detected   │  │  C   │     │
│  └──────┘  └──────┘  └──────┘  └──────┘     │
│                          │                   │
│                          ▼                   │
│                  ┌───────────────┐          │
│                  │ Tool Executor │          │
│                  └───────────────┘          │
│                          │                   │
│                          ▼                   │
│                  ┌───────────────┐          │
│                  │   Continue    │──────────┘
│                  │   Generation  │
│                  └───────────────┘
```

### Tool Call Interface

```kotlin
interface ToolExecutor {
    suspend fun execute(tool: ToolCall): ToolResult
    fun canHandle(toolName: String): Boolean
}

class StreamingToolCaller(
    private val executor: ToolExecutor
) {
    suspend fun processWithTools(
        stream: TokenStream
    ): Flow<ToolCallEvent> = flow {
        stream.collect { token ->
            emit(TokenEvent(token))
            
            if (token.isToolCallStart()) {
                val toolCall = parseToolCall(token)
                val result = executor.execute(toolCall)
                emit(ToolResultEvent(toolCall.id, result))
            }
        }
    }
}
```

## Edge-Cloud Hybrid Mode

When on-device capability is insufficient, delegate to cloud with privacy-preserving protocols.

### Delegation Decision Tree

```
User Request
     │
     ▼
┌─────────────────┐
│ On-Device OK?   │──No──▶ Privacy Check
└────────┬────────┘         │
         │Yes               ▼
         ▼            ┌─────────────────┐
    Process          │ User Consent?  │──No──▶ Partial Result
    On-Device        └────────┬────────┘
                              │Yes
                              ▼
                         Delegate to Cloud
                         (anonymized context)
```

### Privacy-Preserving Cloud Delegation

```kotlin
class HybridInferenceGateway(
    private val localEngine: InferenceEngine,
    private val cloudClient: CloudInferenceClient
) {
    enum class DelegationMode {
        ON_DEVICE_ONLY,     // Never cloud
        ON_DEVICE_FIRST,    // Try local, fall back
        CLOUD_IF_NEEDED,    // User-prompted
        PRIVILEGED_CLOUD    // Explicit consent
    }
    
    suspend fun infer(
        request: InferenceRequest,
        mode: DelegationMode
    ): InferenceResult {
        return when (mode) {
            DelegationMode.ON_DEVICE_ONLY ->
                localEngine.infer(request)
                
            DelegationMode.ON_DEVICE_FIRST ->
                tryLocalFirst(request)
                
            DelegationMode.CLOUD_IF_NEEDED ->
                if (needsCloud(request)) {
                    requireConsent(request)
                    anonymizeAndDelegate(request)
                } else {
                    localEngine.infer(request)
                }
                
            DelegationMode.PRIVILEGED_CLOUD ->
                anonymizeAndDelegate(request)
        }
    }
    
    private fun anonymizeAndDelegate(
        request: InferenceRequest
    ): InferenceResult {
        val anonymized = request.stripPII()
        val sessionId = generateBlindSessionId()
        return cloudClient.infer(anonymized, sessionId)
    }
}
```

### What Never Leaves the Device

| Data Category | On-Device | Cloud (Anonymized) |
|---------------|-----------|-------------------|
| Conversation history | ✅ | ❌ |
| User preferences | ✅ | ❌ |
| Task context | ✅ | Stripped |
| General knowledge queries | ✅ | ✅ |
| Model weights | ✅ | ❌ |

## Power & Thermal Management

Optimize inference for battery life and thermal constraints.

### Power Modes

```kotlin
enum class PowerMode {
    MAX_PERFORMANCE,  // Full GPU/NPU, fastest inference
    BALANCED,         // Dynamic frequency scaling
    POWER_SAVER,      // CPU only, reduced quality
    THERMAL_THROTTLE  // Emergency mode when hot
}

class PowerManager {
    private var currentMode = PowerMode.BALANCED
    
    fun adjustForThermal(tempCelsius: Float) {
        currentMode = when {
            tempCelsius > 45 -> PowerMode.THERMAL_THROTTLE
            tempCelsius > 40 -> PowerMode.POWER_SAVER
            tempCelsius > 35 -> PowerMode.BALANCED
            else -> PowerMode.MAX_PERFORMANCE
        }
    }
    
    fun getInferenceConfig(): InferenceConfig {
        return when (currentMode) {
            PowerMode.MAX_PERFORMANCE -> InferenceConfig(
                useNpu = true,
                threads = Runtime.getRuntime().availableProcessors(),
                batchSize = 32,
                quality = Quality.HIGH
            )
            PowerMode.BALANCED -> InferenceConfig(
                useNpu = true,
                threads = 4,
                batchSize = 16,
                quality = Quality.MEDIUM
            )
            PowerMode.POWER_SAVER -> InferenceConfig(
                useNpu = false,
                threads = 2,
                batchSize = 4,
                quality = Quality.LOW
            )
            PowerMode.THERMAL_THROTTLE -> InferenceConfig(
                useNpu = false,
                threads = 1,
                batchSize = 1,
                quality = Quality.MINIMAL
            )
        }
    }
}
```

### Battery Impact Estimates

| Task Type | Duration | Battery Drain |
|-----------|----------|---------------|
| Chat response (INT4) | ~10s | 1-2% |
| Code generation | ~30s | 3-5% |
| Long document analysis | ~2min | 8-12% |
| RAG with large context | ~5min | 15-20% |

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
