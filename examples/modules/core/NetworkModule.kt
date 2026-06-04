package com.yuangungun.os.core.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/**
 * Minimal HTTP client for offline-first operations.
 * Designed for local AI inference coordination.
 */
class NetworkModule(
    private val baseUrl: String = "http://localhost:8080"
) {
    private val connectionPool = mutableMapOf<String, HttpURLConnection>()

    suspend fun get(path: String): Result<Response> = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl$path")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 5000
            conn.readTimeout = 10000

            val body = conn.inputStream.bufferedReader().readText()
            Result.success(Response(conn.responseCode, body))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun post(path: String, body: String): Result<Response> = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl$path")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.connectTimeout = 5000
            conn.readTimeout = 10000

            conn.outputStream.write(body.toByteArray())
            val responseBody = conn.inputStream.bufferedReader().readText()
            Result.success(Response(conn.responseCode, responseBody))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun close() {
        connectionPool.values.forEach { it.disconnect() }
        connectionPool.clear()
    }

    data class Response(val code: Int, val body: String)
}
