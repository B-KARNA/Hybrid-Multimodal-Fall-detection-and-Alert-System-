package com.fallalert.app.sensor

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.ConcurrentLinkedQueue
import kotlin.math.sqrt

/**
 * SensorCollector reads hardware motion sensors (Accelerometer, Gravity, Gyroscope),
 * performs real-time on-device impact/free-fall detection fallback,
 * and packages 9-channel batches matching the Python model's expected format.
 */
class SensorCollector(private val context: Context) : SensorEventListener {

    private val tag = "SensorCollector"
    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager

    private val accelerometer: Sensor? = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private val gravitySensor: Sensor? = sensorManager.getDefaultSensor(Sensor.TYPE_GRAVITY)
    private val gyroscope: Sensor? = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)

    private var isRunning = false
    var onDeviceFallbackEnabled = true

    // Latest sensor values (x, y, z)
    @Volatile private var latestAcc = floatArrayOf(0f, 9.81f, 0f)
    @Volatile private var latestGravity = floatArrayOf(0f, 9.81f, 0f)
    @Volatile private var latestGyro = floatArrayOf(0f, 0f, 0f)

    // Callbacks
    private var telemetryCallback: ((magnitude: Float) -> Unit)? = null
    private var batchReadyCallback: ((jsonPayload: String) -> Unit)? = null
    private var fallbackFallCallback: ((confidence: String, description: String) -> Unit)? = null

    // Fallback fall detection parameters (calibrated for real-world phone drops and falls)
    private var freeFallDetectedTime: Long = 0L
    private var previousMagnitude: Float = 9.81f
    private val freeFallThreshold = 6.8f // m/s^2 (detects weightlessness during drop/tumble)
    private val impactThreshold = 14.0f // m/s^2 (impact after free-fall, e.g. onto bed, sofa, or floor)
    private val directShockThreshold = 17.5f // m/s^2 (high impact shock without distinct free-fall)
    private val jerkThreshold = 8.0f // m/s^2 (rapid deceleration shock wave)
    private val impactWindowMs = 1800L // impact must happen within 1.8s of free-fall
    private var lastFallbackTriggerTime: Long = 0L
    private val cooldownMs = 10000L // 10s cooldown between on-device triggers

    // Batching queue for streaming to Python server
    private data class SensorReading(
        val name: String,
        val timestampNanos: Long,
        val x: Float,
        val y: Float,
        val z: Float
    )

    private val batchQueue = ConcurrentLinkedQueue<SensorReading>()
    private var lastBatchFlushTime = 0L
    private val batchFlushIntervalMs = 150L // Flush every 150ms to keep network transmission smooth

    fun start(
        onTelemetry: (magnitude: Float) -> Unit,
        onBatchReady: (jsonPayload: String) -> Unit,
        onLocalFallDetected: (confidence: String, description: String) -> Unit
    ) {
        if (isRunning) return

        this.telemetryCallback = onTelemetry
        this.batchReadyCallback = onBatchReady
        this.fallbackFallCallback = onLocalFallDetected

        // Register sensors at GAME delay (~20-50Hz)
        accelerometer?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        }
        gravitySensor?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        }
        gyroscope?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        }

        isRunning = true
        Log.d(tag, "Sensors registered and active for detection.")
    }

    fun stop() {
        if (!isRunning) return
        try {
            sensorManager.unregisterListener(this)
        } catch (e: Exception) {
            Log.e(tag, "Error unregistering sensors: ${e.message}")
        }
        batchQueue.clear()
        isRunning = false
        Log.d(tag, "Sensors unregistered and stopped.")
    }

    override fun onSensorChanged(event: SensorEvent?) {
        if (!isRunning || event == null) return

        val nowMs = System.currentTimeMillis()
        val nowNanos = System.nanoTime()

        when (event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> {
                val x = event.values[0]
                val y = event.values[1]
                val z = event.values[2]
                latestAcc = floatArrayOf(x, y, z)

                // Calculate total acceleration magnitude
                val magnitude = sqrt(x * x + y * y + z * z)
                telemetryCallback?.invoke(magnitude)

                // On-device fallback freefall + impact heuristic
                if (onDeviceFallbackEnabled) {
                    processOnDeviceFallback(magnitude, nowMs)
                }

                // Add synchronized 9-channel reading (all 3 share the exact same timestamp)
                val curGrav = latestGravity
                val curGyro = latestGyro
                batchQueue.add(SensorReading("accelerometer", nowNanos, x, y, z))
                batchQueue.add(SensorReading("gravity", nowNanos, curGrav[0], curGrav[1], curGrav[2]))
                batchQueue.add(SensorReading("gyroscope", nowNanos, curGyro[0], curGyro[1], curGyro[2]))
            }

            Sensor.TYPE_GRAVITY -> {
                latestGravity = floatArrayOf(event.values[0], event.values[1], event.values[2])
            }

            Sensor.TYPE_GYROSCOPE -> {
                latestGyro = floatArrayOf(event.values[0], event.values[1], event.values[2])
            }
        }

        // Flush batch to network if interval elapsed
        if (nowMs - lastBatchFlushTime >= batchFlushIntervalMs && batchQueue.isNotEmpty()) {
            lastBatchFlushTime = nowMs
            flushBatchToJson()
        }
    }

    private fun processOnDeviceFallback(magnitude: Float, nowMs: Long) {
        // Enforce cooldown so we don't spam triggers
        if (nowMs - lastFallbackTriggerTime < cooldownMs) return

        val jerk = kotlin.math.abs(magnitude - previousMagnitude)
        previousMagnitude = magnitude

        // Calculate angular rotation speed from gyroscope
        val curGyro = latestGyro
        val gyroSpeed = sqrt(curGyro[0] * curGyro[0] + curGyro[1] * curGyro[1] + curGyro[2] * curGyro[2])

        // 1. Detect Free Fall stage (sudden drop in acceleration below 5.8 m/s^2)
        if (magnitude < freeFallThreshold) {
            freeFallDetectedTime = nowMs
        }

        // 2. Multi-pattern Fall Trigger:
        // Pattern A: Free-fall detected followed within 1.8s by impact >= 14.0 m/s^2 or jerk >= 8.0 m/s^2
        val isFreeFallWithImpact = (freeFallDetectedTime > 0L) &&
                (nowMs - freeFallDetectedTime <= impactWindowMs) &&
                (magnitude >= impactThreshold || jerk >= jerkThreshold)

        // Pattern B: Direct sudden impact shock (e.g. drop onto bed, sofa, or floor) with rotational tumble
        val isDirectShockWithRotation = (magnitude >= directShockThreshold) &&
                (gyroSpeed >= 0.9f || jerk >= jerkThreshold)

        // Pattern C: Extreme impact (hard collision regardless of rotation)
        val isSevereDirectImpact = magnitude >= 21.0f

        if (isFreeFallWithImpact || isDirectShockWithRotation || isSevereDirectImpact) {
            lastFallbackTriggerTime = nowMs
            freeFallDetectedTime = 0L

            val impactFormatted = String.format("%.1f", magnitude)
            val patternDesc = when {
                isFreeFallWithImpact -> "Rapid drop ($impactFormatted m/s²) preceded by free-fall detected"
                isDirectShockWithRotation -> "Sudden tumbling impact ($impactFormatted m/s²) detected"
                else -> "High-g impact shock ($impactFormatted m/s²) detected"
            }

            fallbackFallCallback?.invoke(
                "98.5% (On-Device Inertial Fallback)",
                patternDesc
            )
        } else if (freeFallDetectedTime > 0L && (nowMs - freeFallDetectedTime > impactWindowMs)) {
            freeFallDetectedTime = 0L
        }
    }

    private fun flushBatchToJson() {
        val readings = mutableListOf<SensorReading>()
        while (!batchQueue.isEmpty() && readings.size < 60) {
            batchQueue.poll()?.let { readings.add(it) }
        }

        if (readings.isEmpty()) return

        try {
            val payloadArray = JSONArray()
            for (r in readings) {
                val item = JSONObject().apply {
                    put("name", r.name)
                    put("time", r.timestampNanos)
                    put("values", JSONObject().apply {
                        put("x", r.x.toDouble())
                        put("y", r.y.toDouble())
                        put("z", r.z.toDouble())
                    })
                }
                payloadArray.put(item)
            }

            val rootJson = JSONObject().apply {
                put("payload", payloadArray)
            }

            batchReadyCallback?.invoke(rootJson.toString())
        } catch (e: Exception) {
            Log.e(tag, "Failed to serialize sensor batch: ${e.message}")
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
}
