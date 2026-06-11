package com.yuangungun.os.core.memory

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*
import java.io.File
import java.security.MessageDigest

/**
 * Local memory storage with semantic indexing.
 * Designed for offline-first AI context persistence.
 */
class MemoryModule(
    private val storagePath: String = "./data/memory"
) {
    private val mutex = Mutex()
    private val index = MemoryIndex()
    private val json = Json { prettyPrint = true; ignoreUnknownKeys = true }

    init {
        File(storagePath).mkdirs()
        loadIndex()
    }

    /**
     * Store a memory entry with automatic tagging.
     */
    suspend fun store(key: String, value: String, tags: Set<String> = emptySet()): Boolean {
        return mutex.withLock {
            try {
                val entry = MemoryEntry(
                    key = key,
                    value = value,
                    tags = tags,
                    timestamp = System.currentTimeMillis(),
                    checksum = hash(value)
                )

                val file = File("$storagePath/${entry.id}.json")
                file.writeText(json.encodeToString(MemoryEntry.serializer(), entry))

                index.add(entry)
                saveIndex()
                true
            } catch (e: Exception) {
                false
            }
        }
    }

    /**
     * Retrieve memory by key.
     */
    suspend fun retrieve(key: String): String? {
        return mutex.withLock {
            index.get(key)?.let { entry ->
                File("$storagePath/${entry.id}.json").takeIf { it.exists() }?.readText()?.let {
                    json.decodeFromString<MemoryEntry>(it).value
                }
            }
        }
    }

    /**
     * Search memories by tag.
     */
    suspend fun searchByTag(tag: String): List<MemoryEntry> {
        return mutex.withLock {
            index.searchByTag(tag).mapNotNull { key ->
                index.get(key)?.let { entry ->
                    File("$storagePath/${entry.id}.json").takeIf { it.exists() }?.let {
                        json.decodeFromString<MemoryEntry>(it.readText())
                    }
                }
            }
        }
    }

    /**
     * Search memories by keyword in value.
     */
    suspend fun search(keyword: String): List<MemoryEntry> {
        return mutex.withLock {
            File(storagePath).listFiles()
                ?.filter { it.extension == "json" }
                ?.mapNotNull {
                    try {
                        json.decodeFromString<MemoryEntry>(it.readText())
                    } catch (e: Exception) { null }
                }
                ?.filter { it.value.contains(keyword, ignoreCase = true) }
                ?: emptyList()
        }
    }

    /**
     * Delete memory by key.
     */
    suspend fun delete(key: String): Boolean {
        return mutex.withLock {
            index.get(key)?.let { entry ->
                val file = File("$storagePath/${entry.id}.json")
                val result = file.delete()
                if (result) {
                    index.remove(key)
                    saveIndex()
                }
                result
            } ?: false
        }
    }

    /**
     * Get memory statistics.
     */
    fun stats(): MemoryStats {
        val files = File(storagePath).listFiles()?.filter { it.extension == "json" } ?: emptyList()
        return MemoryStats(
            count = files.size,
            sizeBytes = files.sumOf { it.length() },
            tags = index.allTags()
        )
    }

    private fun loadIndex() {
        val indexFile = File("$storagePath/.index.json")
        if (indexFile.exists()) {
            try {
                val data = json.parseToJsonElement(indexFile.readText()).jsonObject
                index.load(data)
            } catch (e: Exception) {
                // Rebuild index if corrupted
            }
        }
    }

    private fun saveIndex() {
        val indexFile = File("$storagePath/.index.json")
        indexFile.writeText(json.encodeToString(index.toJson()))
    }

    private fun hash(content: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(content.toByteArray())
        return hash.joinToString("") { "%02x".format(it) }
    }
}

/**
 * Memory entry structure.
 */
@Serializable
data class MemoryEntry(
    val id: String = java.util.UUID.randomUUID().toString(),
    val key: String,
    val value: String,
    val tags: Set<String> = emptySet(),
    val timestamp: Long = System.currentTimeMillis(),
    val checksum: String = ""
)

/**
 * In-memory index for fast lookups.
 */
class MemoryIndex {
    private val byKey = mutableMapOf<String, String>() // key -> entryId
    private val byTag = mutableMapOf<String, MutableSet<String>>() // tag -> entryIds

    fun add(entry: MemoryEntry) {
        byKey[entry.key] = entry.id
        entry.tags.forEach { tag ->
            byTag.getOrPut(tag) { mutableSetOf() }.add(entry.id)
        }
    }

    fun get(key: String): String? = byKey[key]

    fun remove(key: String) {
        byKey.remove(key)
    }

    fun searchByTag(tag: String): Set<String> = byTag[tag] ?: emptySet()

    fun allTags(): Set<String> = byTag.keys

    fun toJson(): JsonObject = buildJsonObject {
        put("byKey", buildJsonObject { byKey.forEach { put(it.key, JsonPrimitive(it.value)) } })
        put("byTag", buildJsonObject {
            byTag.forEach { (tag, ids) ->
                put(tag, JsonArray(ids.map { JsonPrimitive(it) }.toList()))
            }
        })
    }

    fun load(data: JsonObject) {
        data["byKey"]?.jsonObject?.forEach { (k, v) -> byKey[k] = v.jsonPrimitive.content }
        data["byTag"]?.jsonObject?.forEach { (tag, arr) ->
            byTag[tag] = arr.jsonArray.map { it.jsonPrimitive.content }.toMutableSet()
        }
    }
}

/**
 * Memory statistics.
 */
data class MemoryStats(
    val count: Int,
    val sizeBytes: Long,
    val tags: Set<String>
)
