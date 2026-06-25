//
//  SkillPlugin.swift
//  YuánGūnGūn OS - iOS Skill Plugin Example
//
//  © 2026 YuánGūnGūn & ShadowEdge Team
//

import Foundation
import UIKit

/// Protocol for skill plugin lifecycle
public protocol SkillPluginProtocol {
    var skillId: String { get }
    var skillName: String { get }
    var version: String { get }
    
    func initialize(config: [String: Any]) async throws
    func execute(input: SkillInput) async throws -> SkillOutput
    func cleanup() async
}

/// Base input structure for skill plugins
public struct SkillInput: Codable {
    public let userQuery: String
    public let context: [String: String]?
    public let parameters: [String: Any]?
    
    public init(query: String, context: [String: String]? = nil, params: [String: Any]? = nil) {
        self.userQuery = query
        self.context = context
        self.parameters = params
    }
}

/// Base output structure for skill plugins
public struct SkillOutput: Codable {
    public let result: String
    public let confidence: Float
    public let metadata: [String: String]?
    
    public init(result: String, confidence: Float = 1.0, meta: [String: String]? = nil) {
        self.result = result
        self.confidence = confidence
        self.metadata = meta
    }
}

/// Example skill plugin: Text Analyzer
@objc public class TextAnalyzerSkill: NSObject, SkillPluginProtocol {
    
    public let skillId = "text_analyzer_v1"
    public let skillName = "Text Analyzer"
    public let version = "1.0.0"
    
    public func initialize(config: [String: Any]) async throws {
        // Initialize skill resources
        print("TextAnalyzerSkill initialized with config: \(config)")
    }
    
    public func execute(input: SkillInput) async throws -> SkillOutput {
        let text = input.userQuery
        
        // Analyze text metrics
        let wordCount = text.split(separator: " ").count
        let charCount = text.count
        let sentiment = analyzeSentiment(text)
        
        let result = """
        Analysis Results:
        - Words: \(wordCount)
        - Characters: \(charCount)
        - Sentiment: \(sentiment)
        """
        
        return SkillOutput(
            result: result,
            confidence: 0.95,
            meta: ["wordCount": "\(wordCount)"]
        )
    }
    
    public func cleanup() async {
        // Release resources
    }
    
    private func analyzeSentiment(_ text: String) -> String {
        let positiveWords = ["good", "great", "excellent", "amazing", "love", "happy"]
        let negativeWords = ["bad", "terrible", "awful", "hate", "sad", "angry"]
        
        let lowercased = text.lowercased()
        let positive = positiveWords.filter { lowercased.contains($0) }.count
        let negative = negativeWords.filter { lowercased.contains($0) }.count
        
        if positive > negative { return "Positive" }
        if negative > positive { return "Negative" }
        return "Neutral"
    }
}

/// Factory for creating skill instances
public class SkillPluginFactory {
    
    public static let shared = SkillPluginFactory()
    
    private var registry: [String: () -> SkillPluginProtocol] = [:]
    
    private init() {
        registerDefaultSkills()
    }
    
    private func registerDefaultSkills() {
        registry["text_analyzer_v1"] = { TextAnalyzerSkill() }
    }
    
    public func register(skillId: String, factory: @escaping () -> SkillPluginProtocol) {
        registry[skillId] = factory
    }
    
    public func create(skillId: String) -> SkillPluginProtocol? {
        return registry[skillId]?()
    }
    
    public var availableSkills: [String] {
        return Array(registry.keys)
    }
}

// MARK: - UI Integration Extension
extension TextAnalyzerSkill {
    
    /// Generate analysis view for iOS display
    func createAnalysisView(input: String) -> UIView {
        let container = UIView()
        container.backgroundColor = .systemBackground
        
        let label = UILabel()
        label.text = "Analyzing: \(input.prefix(50))..."
        label.font = .monospacedSystemFont(ofSize: 14, weight: .regular)
        label.textColor = .label
        label.numberOfLines = 0
        
        container.addSubview(label)
        label.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            label.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: 16),
            label.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -16),
            label.centerYAnchor.constraint(equalTo: container.centerYAnchor)
        ])
        
        return container
    }
}
