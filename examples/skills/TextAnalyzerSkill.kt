package com.yuangungun.os.skills

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Example skill demonstrating the skill development pattern.
 * Processes text and returns structured analysis.
 */
class TextAnalyzerSkill : YuánGūnGūnSkill {
    override val skillId = "text-analyzer"
    override val name = "Text Analyzer"
    override val version = "1.0.0"

    override suspend fun execute(context: SkillContext): SkillResult {
        return withContext(Dispatchers.Default) {
            val input = context.getInput<String>() ?: return@withContext SkillResult.failure("No input")

            val words = input.trim().split("\\s+".toRegex())
            val sentences = input.split("[.!?]+".toRegex()).filter { it.isNotBlank() }

            SkillResult.success(
                mapOf(
                    "wordCount" to words.size,
                    "sentenceCount" to sentences.size,
                    "avgWordLength" to words.map { it.length }.average(),
                    "keywords" to extractKeywords(input)
                )
            )
        }
    }

    override fun getSchema() = SkillSchema(
        id = skillId,
        name = name,
        inputType = "string",
        outputType = "object",
        description = "Analyzes text and extracts metrics"
    )

    private fun extractKeywords(text: String): List<String> {
        val stopWords = setOf("the", "a", "an", "is", "are", "was", "were", "be", "been", "being")
        return text.lowercase()
            .split("\\W+".toRegex())
            .filter { it.length > 4 && it !in stopWords }
            .groupingBy { it }
            .eachCount()
            .entries
            .sortedByDescending { it.value }
            .take(5)
            .map { it.key }
    }
}

/**
 * Base interfaces - implement in your OS core
 */
interface YuánGūnGūnSkill {
    val skillId: String
    val name: String
    val version: String
    suspend fun execute(context: SkillContext): SkillResult
    fun getSchema(): SkillSchema
}

data class SkillContext(val skillBridge: SkillBridge) {
    fun getInput<T>(): T? = skillBridge.getInput()
}

data class SkillResult(
    val success: Boolean,
    val data: Any? = null,
    val error: String? = null
) {
    companion object {
        fun success(data: Any?) = SkillResult(true, data)
        fun failure(error: String) = SkillResult(false, error = error)
    }
}

data class SkillSchema(
    val id: String,
    val name: String,
    val inputType: String,
    val outputType: String,
    val description: String
)

interface SkillBridge {
    fun <T> getInput(): T?
    fun setOutput(data: Any?)
}
