# Core Modules

Reusable module templates for YuánGūnGūn OS.

## Structure

```
modules/
├── core/
│   ├── network/
│   ├── dispatch/
│   └── crypto/
└── README.md
```

## Core Interface

All modules implement `YuánGūnGūnModule`:

```kotlin
interface YuánGūnGūnModule {
    val name: String
    val version: String
    suspend fun initialize()
    suspend fun destroy()
}
```

> © 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
