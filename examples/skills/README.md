# Skills

Build custom skills that extend YuánGūnGūn OS capabilities.

## Skill Contract

```kotlin
interface YuánGūnGūnSkill {
    val skillId: String
    val name: String
    val version: String
    suspend fun execute(context: SkillContext): SkillResult
    fun getSchema(): SkillSchema
}
```

## Directory Structure

```
skills/
├── skill-template/
│   ├── SKILL.md
│   ├── main.kt
│   └── schema.json
└── README.md
```

## Lifecycle

1. **Install** — Register skill with OS
2. **Initialize** — Load resources, setup dependencies
3. **Execute** — Process requests via skill bridge
4. **Destroy** — Cleanup resources

> © 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
