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
```

## Project Structure

```
ios/
├── YuánGūnGūn/          # Main app target
│   ├── App/             # App entry point
│   ├── Core/            # Biological modules
│   ├── Cardiace/        # Heartbeat
│   ├── Immune/          # Defense
│   ├── Neural/          # Neural network
│   ├── Crypto/          # Encryption
│   ├── Memory/          # Storage
│   ├── Inference/       # Local LLM
│   ├── Features/        # UI modules
│   ├── Chat/
│   ├── Camera/
│   ├── Skills/
│   └── Resources/       # Assets
├── YuánGūnGūnKit/       # Framework
├── Tests/               # Unit tests
└── Podfile
```

## Architecture

- **SwiftUI**: Modern declarative UI
- **Combine**: Reactive programming
- **CoreML**: On-device inference
- **Security Framework**: Keychain, encryption

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
  pod 'Alamofire', '~> 5.8'
  pod 'KeychainAccess', '~> 4.2'
end
```

## Development

**Run on device**: Connect device → Select target → Run (⌘R)

**Build for simulator**: Select iPhone simulator → Cmd+R

**Archive for App Store**: Product → Archive → Distribute

## Troubleshooting

**Pod install fails**: Run `pod repo update` then retry

**Signing errors**: Check Apple Developer account in Xcode → Preferences → Accounts

**Build memory**: Close other apps, increase derived data cleanup frequency

---

## Simulator Configuration

### Device Matrix

| Device | iOS | Chip Target | Use Case |
|--------|-----|-------------|----------|
| iPhone 15 Pro | 17.0 | A17 Pro | Reference flagship |
| iPhone SE (3rd) | 17.0 | A15 | Baseline neural engine |
| iPad Pro M2 | 17.0 | M2 | Tablet split-view |
| Apple Watch Ultra 2 | 10.0 | S9 | Compact UI verification |

```bash
# List available devices
xcrun simctl list devices available

# Boot specific runtime
xcrun simctl boot "iPhone 15 Pro"

# Install + launch
xcrun simctl install booted ./build/Build/Products/Debug-iphonesimulator/YuánGūnGūn.app
xcrun simctl launch booted org.yuangungun.os
```

### Overriding Neural Engine Workloads

```swift
// YuánGūnGūn/Inference/DeviceTier.swift
enum DeviceTier {
    case lite, pro, ultra

    static func detect() -> DeviceTier {
        let bytes = ProcessInfo.processInfo.physicalMemory
        switch bytes {
        case ..<4_000_000_000:  return .lite
        case ..<8_000_000_000:  return .pro
        default:                return .ultra
        }
    }

    var maxContextTokens: Int {
        switch self {
        case .lite:  return 1024
        case .pro:   return 4096
        case .ultra: return 8192
        }
    }
}
```

## Instruments Workflow

### Time Profiler — Inference Hot Path

```text
1. Product → Profile → Time Profiler
2. Record during 30s of LLM inference
3. Inspect call tree → CoreML → ANE
4. Look for: malloc stack > 5%  → tune buffer pool
5. Look for: ANEUtilization < 60% → increase batch
```

### Allocations — Memory Chain

```text
1. Product → Profile → Allocations
2. Filter by "MemoryChain" symbol
3. Verify zero leaks across 10 chat cycles
4. Mark generational regions for diff
```

### CLI Trace Export

```bash
# Headless trace (CI-friendly)
xcrun xctrace record \
  --template "Time Profiler" \
  --device-name "iPhone 15 Pro" \
  --time-limit 30s \
  --output trace.xctrace
xcrun xctrace export --input trace.xctrace \
  --xpath '/trace-toc/run[1]/data/table[0]' > profile.csv
```

## TestFlight Distribution

| Stage | Action | Result |
|-------|--------|--------|
| Archive | Product → Archive | `.xcarchive` |
| Validate | Organizer → Validate App | Pre-submit checks |
| Distribute | Organizer → Distribute App → App Store Connect | Build appears in TestFlight |
| Internal | App Store Connect → TestFlight → Internal Group | Auto-install on registered devices |
| External | TestFlight → External Group → Add build | Beta review (1-2 days) |

```bash
# Upload via altool (deprecated, use Transporter)
xcrun altool --upload-app \
  --type ios \
  --file "YuánGūnGūn.ipa" \
  --username "$ASC_APP_ID" \
  --password "$ASC_APP_PW"
```

## App Store Submission

### Pre-flight Checklist

- [ ] App icon 1024×1024 (no alpha)
- [ ] Launch screen storyboard
- [ ] Privacy manifest (`PrivacyInfo.xcprivacy`)
- [ ] App Privacy details on App Store Connect
- [ ] Export compliance (encryption usage)
- [ ] App Tracking Transparency strings (if applicable)
- [ ] Localization for primary markets

### Archive & Submit

```text
1. Product → Archive
2. Organizer → Distribute App → App Store Connect → Upload
3. App Store Connect → My Apps → YuánGūnGūn → + Version
4. Fill metadata, screenshots, privacy
5. Select build from TestFlight
6. Submit for Review
```

## Privacy Manifest

```xml
<!-- PrivacyInfo.xcprivacy -->
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>NSPrivacyTracking</key>
    <false/>
    <key>NSPrivacyTrackingDomains</key>
    <array/>
    <key>NSPrivacyCollectedDataTypes</key>
    <array>
        <dict>
            <key>NSPrivacyCollectedDataType</key>
            <string>NSPrivacyCollectedDataTypeOtherDiagnosticData</string>
            <key>NSPrivacyCollectedDataTypeLinked</key>
            <false/>
            <key>NSPrivacyCollectedDataTypeTracking</key>
            <false/>
            <key>NSPrivacyCollectedDataTypePurposes</key>
            <array><string>NSPrivacyCollectedDataTypePurposeAnalytics</string></array>
        </dict>
    </array>
    <key>NSPrivacyAccessedAPITypes</key>
    <array>
        <dict>
            <key>NSPrivacyAccessedAPIType</key>
            <string>NSPrivacyAccessedAPICategoryFileTimestamp</string>
            <key>NSPrivacyAccessedAPITypeReasons</key>
            <array><string>C617.1</string></array>
        </dict>
    </array>
</dict>
</plist>
```

## Continuous Integration

### Fastlane

```ruby
# fastlane/Fastfile
default_platform(:ios)

platform :ios do
  desc "Run unit + UI tests"
  lane :test do
    run_tests(
      scheme: "YuánGūnGūn",
      devices: ["iPhone 15 Pro"],
      result_bundle: true
    )
  end

  desc "Release build to TestFlight"
  lane :beta do
    increment_build_number_in_xcodeproj
    build_app(workspace: "YuánGūnGūn.xcworkspace",
              scheme: "YuánGūnGūn",
              export_method: "app-store")
    upload_to_testflight(skip_waiting_for_build_processing: true)
  end
end
```

### GitHub Actions — iOS

```yaml
# .github/workflows/ios.yml
name: iOS CI
on: [push, pull_request]

jobs:
  test:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4
      - name: Select Xcode
        run: sudo xcode-select -s /Applications/Xcode_15.4.app
      - name: Cache CocoaPods
        uses: actions/cache@v4
        with:
          path: Pods
          key: ${{ runner.os }}-pods-${{ hashFiles('**/Podfile.lock') }}
      - name: Install pods
        run: pod install
      - name: Run tests
        run: |
          xcodebuild test \
            -workspace YuánGūnGūn.xcworkspace \
            -scheme YuánGūnGūn \
            -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
```

## Common Pitfalls

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Code signing fails | Expired certificate | Xcode → Preferences → Accounts → Download Manual Profiles |
| `dyld: Library not loaded` | Pod not embedded | `use_frameworks!` + `pod install` |
| ANE underutilized | Float32 weights | Convert to `MLMultiArray` with `float16` |
| MemoryChain append deadlock | Shared serial queue contention | Dispatch appends on dedicated actor |
| App Review rejection 2.1 | Crashes on launch | Verify all pods linked; check `Other Linker Flags` |
| Privacy manifest invalid | Missing `NSPrivacyAccessedAPITypeReasons` | Use correct `CA*` reason codes |

---

© 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
