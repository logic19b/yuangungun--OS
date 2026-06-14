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
- **LLM inference** runs locally via MNN
- **Memory stored** in EncryptedSharedPreferences (Android) / Keychain (iOS)
- **No telemetry**, no analytics, no crash reporting

### Encrypted Storage
- **Memory**: XOR + Base64 (key = 0xAA)
- **Financial data**: Separate XOR (key = 0xBB)
- **API keys**: EncryptedSharedPreferences
- **Certificate pinning** prevents MITM

### Network Isolation
Network requests only for:
- **Cloud inference fallback**: Only query text, no context/history
- **Model downloads**: User-triggered only

All traffic: HTTPS + certificate pinning + encrypted keys.

### The Immune System
- **Monitors outputs** for sensitive patterns
- **Blocks data extraction attempts**
- **Isolates suspicious interactions**

---

## Threat Model

### Attack Surface

| Layer | Protection |
|-------|------------|
| Device | Immune System, Pattern Block |
| Storage | AES-256, XOR+Base64 |
| Model | MNN Local Inference |
| Network | TLS 1.3 + Pinning |

### Threat Vectors Mitigated

| Threat | Mitigation |
|--------|------------|
| Memory dump | Encrypted storage, Keychain isolation |
| Network interception | TLS 1.3, Certificate pinning |
| Prompt injection | Immune system monitoring |
| Model extraction | On-device inference only |
| Side-channel attacks | No external telemetry |

---

## Permissions Model

### Minimal Footprint
YuánGūnGūn OS requests only what's necessary:

| Permission | Why | Can be denied |
|------------|-----|---------------|
| Microphone | Voice input | Yes — text-only mode works |
| Storage | Save memories | Yes — ephemeral mode available |
| Network | Cloud fallback | Yes — fully offline mode |

### No Hidden Permissions
- No contacts access
- No location tracking
- No calendar integration (unless explicit)
- No background data collection

---

## Data Rights

### You Own Everything
- **Export**: All your data in portable JSON format
- **Delete**: Complete wipe with single tap
- **No account required**: Works without registration
- **No data recovery**: Deletion is permanent by design

### What We Can't Do (Even If Asked)
1. Access your conversations
2. Recover your deleted data
3. Transfer your memories to another device
4. Provide your data to third parties

---

## Incident Response

### Security Disclosure
Found a vulnerability?

```
Email: security@yuangungun.os
PGP:   Available on request
Response time: 24-48 hours
Bounty: Vulnerability reward program (coming Q3 2026)
```

### Zero-Knowledge Architecture
Even if we're subpoenaed, we can only provide:
- Aggregate app usage statistics (no personal data)
- Technical architecture documentation
- Your encrypted blob (without your device key)

---

## Cloud AI vs YuánGūnGūn OS

| | Cloud AI | YuánGūnGūn OS |
|--|---------|--------------|
| Chat history | Server-side | Device-only |
| Model training | Your data may be used | Never |
| Encryption keys | Company holds | You hold |
| Offline operation | No | Yes |
| Auditability | Trust-based | Architecture-verified |

---

## Security Hardening

### Android
- SafetyNet / Play Integrity API
- Hardware-backed keystore
- Scoped storage isolation
- No signature permissions

### iOS
- Secure Enclave integration
- Keychain data protection class: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
- App Transport Security enforced
- No data backup to iCloud (optional)

---

*Privacy isn't a promise. It's an architecture.*

© 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
