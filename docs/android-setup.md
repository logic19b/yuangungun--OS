# Android Setup Guide

## Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| Java JDK | 17 LTS | Gradle 8.x requirement |
| Android Studio | Ladybug+ | Hedgehog for ARM Mac |
| Gradle | 8.4+ | Bundled with Android Studio |
| Android SDK | API 34+ | Target SDK 35 |
| Kotlin | 1.9.x | JVM backend |

## Quick Start

```bash
# Clone repository
git clone https://github.com/logic19b/yuangungun--OS.git
cd yuangungun--OS/android

# Install dependencies
./gradlew dependencies --refresh-dependencies

# Open workspace
open AndroidStudio/yuangungun--OS/android.yuangungun
```

## Project Structure

```
android/
├── app/                           # Main application target
│   ├── src/main/kotlin/          # Kotlin source
│   │   ├── Core/                 # Biological modules
│   │   │   ├── network/          # Neural network simulation
│   │   │   ├── immune/           # Security defense
│   │   │   ├── memory/           # Long-term storage
│   │   │   ├── inference/        # On-device AI
│   │   │   └── recovery/         # Self-healing
│   │   ├── Carousel/             # Heartbeat
│   │   │   └── scheduler/        # Task scheduling
│   │   └── Feature/              # UI modules
│   └── src/main/res/             # Resources
├── framework/                     # Core framework
├── lib/                          # Shared libraries
└── build.gradle.kts              # Build configuration
```

## Architecture

- **UI Layer**: Jetpack Compose, Material 3
- **Domain Layer**: Use cases, business logic
- **Data Layer**: Repository pattern, Room database

## Build Configuration

| Setting | Value |
|---------|-------|
| Compile SDK | 35 |
| Min SDK | 26 |
| Target SDK | 35 |
| Kotlin Version | 1.9.24 |

## Key Dependencies

```kotlin
// Core
implementation("androidx.core:core-ktx:1.13.1")
implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.3")

// Compose
implementation(platform("androidx.compose:compose-bom:2024.06.00"))
implementation("androidx.compose.ui:ui")
implementation("androidx.compose.material3:material3")

// On-device Inference
implementation("com.google.mlkit:on-device-inference:17.0.0")
implementation("com.google.mlkit:smart-reply:17.0.0")

// Security
implementation("androidx.security:security-crypto:1.1.0-alpha06")
implementation("androidx.biometric:biometric:1.1.0")

// LocalLLM
implementation("com.github.NeoMindAI:LocalLLM:v2.0.0")
```

## Build Commands

```bash
# Debug build
./gradlew assembleDebug

# Release build
./gradlew assembleRelease

# Run on device
./gradlew installDebug

# Clean build
./gradlew clean

# Run tests
./gradlew test
```

## Troubleshooting

**Gradle sync fails**: Run `./gradlew wrapper --gradle-version=8.4` to update wrapper

**Out of memory**: Increase heap size in `gradle.properties`:
```properties
org.gradle.jvmargs=-Xmx4096m -Dfile.encoding=UTF-8
```

**SDK not found**: Set `ANDROID_HOME` in `local.properties`:
```properties
sdk.dir=/Users/username/Library/Android/sdk
```

**ARM Mac performance**: Use Rosetta for Intel-only dependencies

---

## Device & Emulator Configuration

### Virtual Device Profiles

| Profile | Use Case | RAM | API |
|---------|----------|-----|-----|
| Pixel 7 | Reference form factor | 8 GB | 34 |
| Pixel Fold | Foldable path | 12 GB | 34 |
| Wear OS Square | Compact widget | 1 GB | 33 |
| Automotive | Head-unit projection | 4 GB | 32 |

```bash
# Create AVD via avdmanager
$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager create avd \
  -n Pixel7_Biological \
  -k "system-images;android-34;google_apis;arm64-v8a" \
  -d pixel_7

# Boot with custom heap for on-device inference
emulator -avd Pixel7_Biological -memory 6144 -no-snapshot
```

### Wireless ADB Pairing

```bash
# Phone side: Developer Options → Wireless debugging → Pair
adb pair 192.168.1.42:37845      # Paste pairing code
adb connect 192.168.1.42:37845
adb devices                       # Verify
```

## ADB Advanced Usage

### Biological Module Introspection

```bash
# Trace immune defense activity
adb shell am broadcast -a org.yuangungun.immune.DUMP_STATE \
  --es format json

# Stream heartbeat events
adb logcat -s Carousel:V Heartbeat:V Immune:V

# Memory chain verification
adb shell run-as org.yuangungun.os cat \
  /data/data/org.yuangungun.os/files/memory/chain.lock | sha256sum
```

### Performance Tracing

```bash
# Cold start trace
adb shell am start -W -n org.yuangungun.os/.MainActivity
adb shell atrace --async_start -t 10 sched freq idle

# Method-level sampling
adb shell am profile start \
  org.yuangungun.os /sdcard/trace.trace
# ...interact with the app...
adb shell am profile stop
adb pull /sdcard/trace.trace .
```

## ProGuard / R8 Optimization

### Rules Highlights

```pro
# Keep biological interfaces (reflection-based dispatch)
-keep interface org.yuangungun.core.** { *; }
-keepclassmembers class * implements org.yuangungun.core.Module {
    public <init>(...);
}

# Keep inference entry points
-keep class com.neomind.localllm.** { *; }

# Strip Compose tooling in release
-assumenosideeffects class android.compose.runtime.ComposerKt {
    java.lang.Object traceEventStart(...);
    void traceEventEnd(...);
}
```

### Verification

```bash
# Build with mapping file
./gradlew assembleRelease \
  -PenableR8=true \
  -Pandroid.enableR8.fullMode=true

# Inspect resulting class count
$ANDROID_HOME/build-tools/35.0.0/dexdump \
  app/build/outputs/apk/release/app-release.apk | grep -c "Class descriptor"
```

## Signing & Release Pipeline

| Stage | Tool | Output |
|-------|------|--------|
| Keystore | `keytool -genkey -v -keystore release.jks` | `release.jks` |
| Signing config | Gradle signingConfigs | Wired at `app/build.gradle.kts` |
| Bundle | `./gradlew bundleRelease` | `.aab` for Play |
| Mapping | R8 emits `mapping.txt` | Reverse-deobfuscation |

```kotlin
// app/build.gradle.kts
android {
    signingConfigs {
        create("release") {
            storeFile = file(System.getenv("KEYSTORE_PATH"))
            storePassword = System.getenv("KEYSTORE_PASS")
            keyAlias = System.getenv("KEY_ALIAS")
            keyPassword = System.getenv("KEY_PASS")
        }
    }
    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            isMinifyEnabled = true
            isShrinkResources = true
        }
    }
}
```

## Performance Profiling

| Tool | Measures | Best For |
|------|----------|----------|
| Studio Profiler | CPU · Memory · Network · Energy | Interactive triage |
| Macrobenchmark | Cold/warm start, jank | CI regression gate |
| Baseline Profiles | Critical-path AOT hints | First-render speed |
| Perfetto | Trace visualization | Cross-process deep dive |

```kotlin
// Macrobenchmark sample
@RunWith(AndroidJUnit4::class)
class StartupBenchmark {
    @get:Rule
    val rule = MacrobenchmarkRule()

    @Test
    fun coldStartBiological() {
        rule.measureRepeated(
            packageName = "org.yuangungun.os",
            metrics = listOf(StartupTimingMetric()),
            compilationMode = CompilationMode.DEFAULT,
            startupMode = StartupMode.COLD,
            iterations = 10
        ) {
            pressHome()
            startActivityAndWait()
        }
    }
}
```

## CI/CD Integration

### GitHub Actions — Android

```yaml
# .github/workflows/android.yml
name: Android CI
on: [push, pull_request]

jobs:
  build:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: 17
      - name: Grant execute permission
        run: chmod +x gradlew
      - name: Run unit tests
        run: ./gradlew testDebugUnitTest
      - name: Build release AAB
        run: ./gradlew bundleRelease
        env:
          KEYSTORE_PATH: ${{ secrets.KEYSTORE_PATH }}
          KEYSTORE_PASS: ${{ secrets.KEYSTORE_PASS }}
          KEY_ALIAS: ${{ secrets.KEY_ALIAS }}
          KEY_PASS: ${{ secrets.KEY_PASS }}
      - uses: actions/upload-artifact@v4
        with:
          name: app-release
          path: app/build/outputs/bundle/release/*.aab
```

## Common Pitfalls

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `INSTALL_FAILED_VERSION_DOWNGRADE` | Mismatched versionCode | Bump `versionCode` in `build.gradle.kts` |
| `OutOfMemoryError: PermGen` | Old JDK heap | Use JDK 17, set `-Xmx4096m` |
| Compose recomposition storm | Unstable lambda capture | Wrap in `remember { }` |
| LoRA adapter load slow | Asset unaligned to chunk size | Bundle as `.gguf` with 4 KB chunks |
| ANR in `MemoryChain.append` | Sync SQLite write | Move to `Dispatchers.IO` |

---

© 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
