package com.fallalert.app.sensor

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * Result data class from Python fall detection server requests.
 */
data class NetworkResult(
    val success: Boolean,
    val fallDetected: Boolean = false,
    val probability: Float = 0f,
    val samplesCount: Int = 0,
    val errorMessage: String? = null
)

/**
 * DetectionNetworkClient communicates with the Python fall detection backend.
 * Supports:
 * 1. POSTing raw 9-channel motion sensor batches to the LSTM model.
 * 2. GETting current /status to receive camera/vision fall alerts from PC.
 */
class DetectionNetworkClient {

    private val tag = "DetectionNetworkClient"
    private val connectTimeoutMs = 10000
    private val readTimeoutMs = 10000

    /**
     * Sends sensor batch payload to the Python server root endpoint (POST /).
     */
    suspend fun sendSensorBatch(serverBaseUrl: String, jsonPayload: String): NetworkResult =
        withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val cleanUrl = sanitizeUrl(serverBaseUrl)
                val url = URL(cleanUrl)
                connection = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = connectTimeoutMs
                    readTimeout = readTimeoutMs
                    doOutput = true
                    doInput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    setRequestProperty("Accept", "application/json")
                }

                // Write JSON payload
                OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                    writer.write(jsonPayload)
                    writer.flush()
                }

                val responseCode = connection.responseCode
                if (responseCode in 200..299) {
                    val responseText = connection.inputStream.bufferedReader().use(BufferedReader::readText)
                    parseDetectionResponse(responseText)
                } else {
                    val errorText = connection.errorStream?.bufferedReader()?.use(BufferedReader::readText)
                    NetworkResult(
                        success = false,
                        errorMessage = "Server HTTP $responseCode: ${errorText ?: "Unknown error"}"
                    )
                }
            } catch (e: Exception) {
                Log.w(tag, "sendSensorBatch failed: ${e.message}")
                NetworkResult(
                    success = false,
                    errorMessage = e.message ?: "Failed to connect to Python server"
                )
            } finally {
                connection?.disconnect()
            }
        }

    /**
     * Polls the /status endpoint to receive Vision/Camera fall alerts or server health.
     */
    suspend fun checkServerStatus(serverBaseUrl: String): NetworkResult =
        withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val cleanUrl = sanitizeUrl(serverBaseUrl).trimEnd('/') + "/status"
                val url = URL(cleanUrl)
                connection = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = connectTimeoutMs
                    readTimeout = readTimeoutMs
                    doInput = true
                    setRequestProperty("Accept", "application/json")
                }

                val responseCode = connection.responseCode
                if (responseCode in 200..299) {
                    val responseText = connection.inputStream.bufferedReader().use(BufferedReader::readText)
                    parseDetectionResponse(responseText)
                } else {
                    NetworkResult(
                        success = false,
                        errorMessage = "Status check HTTP $responseCode"
                    )
                }
            } catch (e: Exception) {
                Log.d(tag, "checkServerStatus failed: ${e.message}")
                NetworkResult(
                    success = false,
                    errorMessage = e.message ?: "Status query error"
                )
            } finally {
                connection?.disconnect()
            }
        }

    private fun parseDetectionResponse(jsonString: String): NetworkResult {
        return try {
            val json = JSONObject(jsonString)
            val fall = json.optBoolean("fall", false)
            val probability = json.optDouble("probability", 0.0).toFloat()
            val samples = json.optInt("samples", 0)

            NetworkResult(
                success = true,
                fallDetected = fall,
                probability = probability,
                samplesCount = samples
            )
        } catch (e: Exception) {
            Log.e(tag, "Error parsing JSON response: $jsonString", e)
            NetworkResult(
                success = false,
                errorMessage = "Invalid JSON from server: ${e.message}"
            )
        }
    }

    private fun sanitizeUrl(input: String): String {
        var trimmed = input.trim()
        if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
            trimmed = "http://$trimmed"
        }
        return trimmed.trimEnd('/')
    }
}
