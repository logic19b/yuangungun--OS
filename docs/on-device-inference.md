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


### LoRA Adapter Hub

Lightweight Low-Rank Adaptation (LoRA) adapters enable task-specialized behavior without downloading full models. Each adapter is typically 5-50 MB and composes with the base model at inference time.

#### Adapter Categories

| Category | Size | Use Case |
|----------|------|----------|
| **Code Expert** | ~40 MB | Programming, debugging, code review |
| **Security Analyst** | ~35 MB | Threat detection, vulnerability analysis |
| **Creative Writer** | ~25 MB | Content generation, storytelling |
| **Translation** | ~30 MB | Multilingual translation & localization |
| **Math & Reasoning** | ~45 MB | Complex problem solving, logical deduction |

#### Adapter Routing

The router selects the optimal adapter based on task classification:

```kotlin
class LoRAAdapterHub(
    private val baseModel: InferenceModel,
    private val adapterDir: String
) {
    private val activeAdapters = mutableMapOf<String, LoRAAdapter>()
    private val router = TaskClassifier()

    suspend fun inferWithAdapter(
        prompt: String,
        context: AgentContext
    ): InferenceResult {
        val taskType = router.classify(prompt)
        val adapter = getOrLoadAdapter(taskType)
        
        return baseModel.infer(
            prompt = prompt,
            adapterWeights = adapter?.weights,
            adapterAlpha = adapter?.alpha ?: 1.0f
        )
    }

    private suspend fun getOrLoadAdapter(taskType: TaskType): LoRAAdapter? {
        activeAdapters[taskType.id]?.let { return it }
        
        val adapterPath = "$adapterDir/${taskType.id}.lora"
        if (!File(adapterPath).exists()) return null
        
        val adapter = LoRAAdapterLoader.load(adapterPath)
        activeAdapters[taskType.id] = adapter
        return adapter
    }

    fun availableAdapters(): List<AdapterInfo> =
        File(adapterDir).listFiles { _, name -> name.endsWith(".lora") }
            ?.map { AdapterInfo.fromFile(it) }
            ?: emptyList()
}
```

#### Composable Adapters

Multiple adapters can be composed for hybrid tasks (e.g., code + security for vulnerability analysis):

```kotlin
suspend fun composeInference(
    prompt: String,
    adapterIds: List<String>,
    weights: List<Float>
): InferenceResult {
    val composedWeights = adapterIds.zip(weights).associate { it }
    return baseModel.infer(prompt, composedAdapters = composedWeights)
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

### Memory Pressure Response

```kotlin
sealed class MemoryPressure {
    object Low : MemoryPressure()      // Normal operation
    object Medium : MemoryPressure()   // Pause background tasks
    object High : MemoryPressure()     // Unload idle models
    object Critical : MemoryPressure() // Emergency unloading
}
```


## On-Device Fine-tuning Pipeline

Enable lightweight model adaptation directly on the device using federated learning principles. No raw data ever leaves the device — only lightweight adapter deltas are shared (with explicit consent).

### Fine-tuning Capabilities

| Capability | Method | Data Required | Duration |
|------------|--------|---------------|----------|
| **Vocabulary adaptation** | Embedding fine-tune | 100+ samples | ~2 min |
| **Style alignment** | LoRA rank-8 | 500+ samples | ~10 min |
| **Task specialization** | LoRA rank-16 | 2000+ samples | ~30 min |
| **Domain expert** | Full adapter | 10000+ samples | ~2 hr |

### Training Pipeline

```
User Interactions → Dataset Curation → LoRA Training → Evaluation → Adapter Deploy
         ↓              ↓                ↓              ↓             ↓
    auto-collect   quality filtering   quantized     benchmark     hot-swap
                   privacy scrub       gradient                    without restart
```

### Dataset Curation

```kotlin
class FineTuningDatasetManager(
    private val maxSamples: Int = 5000,
    private val qualityThreshold: Float = 0.8f
) {
    data class TrainingSample(
        val input: String,
        val output: String,
        val qualityScore: Float,
        val source: SampleSource,
        val timestamp: Long
    )

    suspend fun addSample(sample: TrainingSample) {
        if (sample.qualityScore < qualityThreshold) return
        
        val scrubbed = scrubPii(sample)
        val deduplicated = deduplicate(scrubbed)
        
        trainingSamples.add(deduplicated)
        if (trainingSamples.size > maxSamples) {
            evictLowestQuality()
        }
    }

    private fun scrubPii(sample: TrainingSample): TrainingSample {
        val scrubbedInput = piiScrubber.scrub(sample.input)
        val scrubbedOutput = piiScrubber.scrub(sample.output)
        return sample.copy(input = scrubbedInput, output = scrubbedOutput)
    }

    suspend fun buildTrainingSet(size: Int): List<TrainingSample> {
        return trainingSamples
            .sortedByDescending { it.qualityScore }
            .take(size)
    }
}
```

### Adapter Training Engine

```kotlin
class OnDeviceTrainer(
    private val baseModel: InferenceModel,
    private val config: TrainingConfig
) {
    data class TrainingConfig(
        val rank: Int = 8,
        val alpha: Float = 16f,
        val learningRate: Float = 1e-4f,
        val epochs: Int = 3,
        val batchSize: Int = 2,
        val maxDurationMinutes: Int = 30
    )

    sealed class TrainingState {
        data object Idle : TrainingState()
        data class Running(val epoch: Int, val loss: Float, val progress: Float) : TrainingState()
        data class Completed(val adapterPath: String, val evalScore: Float) : TrainingState()
        data class Failed(val reason: String) : TrainingState()
    }

    suspend fun trainAdapter(
        dataset: List<TrainingSample>,
        adapterName: String,
        onProgress: (TrainingState) -> Unit
    ): TrainingState {
        // Check prerequisites: charging + WiFi + idle thermal state
        if (!canTrainNow()) {
            return TrainingState.Failed("Device not ready for training")
        }

        var currentEpoch = 0
        var bestLoss = Float.MAX_VALUE
        
        for (epoch in 0 until config.epochs) {
            currentEpoch = epoch
            val epochLoss = runEpoch(dataset.shuffled(), epoch)
            
            if (epochLoss < bestLoss) {
                bestLoss = epochLoss
                saveCheckpoint(adapterName, epoch)
            }
            
            onProgress(TrainingState.Running(epoch, epochLoss, 
                (epoch + 1f) / config.epochs))
            
            if (thermalManager.isOverheating()) break
        }

        val evalScore = evaluateAdapter(adapterName, dataset.takeLast(100))
        val finalPath = finalizeAdapter(adapterName)
        
        return TrainingState.Completed(finalPath, evalScore)
    }

    private fun canTrainNow(): Boolean {
        return batteryManager.isCharging() &&
               thermalManager.currentTemp() < 35f &&
               connectivityManager.isOnWifi()
    }
}
```

### Training Constraints

- **Charging only** — Training only runs while the device is charging
- **Thermal throttle** — Pauses automatically if device temperature exceeds 38°C
- **WiFi required** — Adapter downloads/uploads only over WiFi (user-configurable)
- **Idle preference** — Scheduled during device idle windows (typically 2-6 AM)
- **Resource budget** — Maximum 20% CPU / 30% GPU utilization during training

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
