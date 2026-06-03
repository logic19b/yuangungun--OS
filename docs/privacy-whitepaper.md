# Privacy Whitepaper

## The Core Promise

**Your data never leaves your device.**

This isn't a privacy policy full of legal loopholes. It's an architectural fact.

---

## Why "Privacy Promises" Aren't Enough

| Claim | Reality |
|-------|---------|
| "We don't sell your data" | They use it to train models |
| "We encrypt your data" | They hold the decryption keys |
| "We comply with regulations" | Governments can still subpoena |
| "We anonymize your data" | Re-identification is well-documented |

If your data is on their servers, you're trusting them. If your data is on your device, you don't need to trust anyone.

---

## Verifiable Privacy

### Local-First Architecture
- LLM inference runs locally via MNN
- Memory stored in EncryptedSharedPreferences (Android) / Keychain (iOS)
- No telemetry, no analytics, no crash reporting

### Encrypted Storage
- Memory: XOR + Base64 (key = 0xAA)
- Financial data: Separate XOR (key = 0xBB)
- API keys: EncryptedSharedPreferences
- Certificate pinning prevents MITM

### Network Isolation
Network requests only for:
- Cloud inference fallback: Only query text, no context/history
- Model downloads: User-triggered only

All traffic: HTTPS + certificate pinning + encrypted keys.

### The Immune System
- Monitors outputs for sensitive patterns
- Blocks data extraction attempts
- Isolates suspicious interactions

---

## Cloud AI vs YuánGūnGūn OS

| | Cloud AI | YuánGūnGūn OS |
|---|---|---|
| Chat history | Server-side | Device-only |
| Model training | Your data may be used | Never |
| Encryption keys | Company holds | You hold |
| Offline operation | No | Yes |
| Auditability | Trust-based | Architecture-verified |

---

**Privacy isn't a promise. It's an architecture.**

© 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
