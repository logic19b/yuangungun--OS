# Android Setup Guide

## Prerequisites

- **Android Studio** Hedgehog or later
- **JDK 17**
- **Android SDK** API 34 (Android 14)
- **NDK** 26.1.10909125
- **Kotlin** 1.9.24
- **Gradle** 8.7

## Quick Start

```bash
git clone https://github.com/logic19b/yuangungun--OS.git
cd yuangungun--OS

# Open in Android Studio → Sync Gradle → Build
./gradlew assembleDebug
```

## Project Structure

```
yuangungun--OS/
├── app/                    # Main application
├── core/
│   ├── cardiac/            # Heartbeat rhythm
│   ├── immune/             # Injection defense
│   ├── metabolic/          # Energy-aware processing
│   ├── circadian/          # Sleep-wake cycles
│   ├── homeostatic/        # Self-regulation
│   ├── subconscious/       # Background memory
│   ├── instinctive/        # Threat detection
│   ├── sleep/              # Consolidation
│   ├── stress/             # Load management
│   ├── forgetting/         # Memory decay
│   ├── network/            # HTTP + security
│   ├── crypto/             # Encryption
│   ├── memory/             # Persistent store
│   ├── dispatch/           # Task dispatch
│   ├── recovery/           # Self-healing
│   ├── dynamic/            # Module loading
│   ├── life/               # Life core
│   └── inference/          # On-device LLM
├── feature/
│   ├── chat/               # Chat interface
│   ├── camera/             # Camera integration
│   └── skills/             # Skill management
└── platform/               # Platform services
```

## Build Config

- **minSdk**: 26 (Android 8.0)
- **targetSdk**: 34 (Android 14)
- **Hilt** for DI
- **Jetpack Compose** for UI
- **KSP** 1.9.22-1.0.17 (not kapt)

---

© 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
