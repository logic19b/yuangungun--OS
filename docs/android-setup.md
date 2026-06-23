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

© 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
