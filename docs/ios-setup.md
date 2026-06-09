# iOS Setup Guide

## Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| Xcode | 15.0+ | App Store |
| Swift | 5.9+ | Bundled with Xcode |
| CocoaPods | 1.14+ | `sudo gem install cocoapods` |
| Homebrew | Latest | Optional package manager |

## Quick Start

```bash
# Clone repository
git clone https://github.com/logic19b/yuangungun--OS.git
cd yuangungun--OS/ios

# Install dependencies
pod install

# Open workspace
open YuánGūnGūn.xcworkspace

# Build (Cmd+B) or Run (Cmd+R)
```

## Project Structure

```
ios/
├── YuánGūnGūn/              # Main app target
│   ├── App/                 # App entry point
│   ├── Core/                # Biological modules
│   │   ├── Cardiac/         # Heartbeat
│   │   ├── Immune/          # Defense
│   │   ├── Network/         # HTTP layer
│   │   ├── Crypto/          # Encryption
│   │   ├── Memory/          # Storage
│   │   └── Inference/       # Local LLM
│   ├── Features/            # UI modules
│   │   ├── Chat/
│   │   ├── Camera/
│   │   └── Skills/
│   └── Resources/          # Assets
├── YuánGūnGūnKit/           # Framework
└── Tests/                   # Unit tests
```

## Architecture

- **SwiftUI** — Modern declarative UI
- **Combine** — Reactive programming
- **CoreML** — On-device inference
- **Security Framework** — Keychain, encryption

## Build Config

| Setting | Value |
|---------|-------|
| iOS Deployment Target | 15.0 |
| Swift Version | 5.9 |
| Enable Bitcode | No |

## Key Dependencies

```ruby
# Podfile
platform :ios, '15.0'
use_frameworks!

target 'YuánGūnGūn' do
  pod 'SnapKit', '~> 5.6'
  pod ' Alamofire', '~> 5.8'
  pod 'KeychainAccess', '~> 4.2'
end
```

## Development

**Run on device**: Connect device → Select target → Run (Cmd+R)

**Build for simulator**: Select iPhone simulator → Cmd+R

**Archive for App Store**: Product → Archive → Distribute

## Troubleshooting

**Pod install fails**: Run `pod repo update` then retry

**Signing errors**: Check Apple Developer account in Xcode → Preferences → Accounts

**Build memory**: Close other apps, increase derived data cleanup frequency

---

© 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
