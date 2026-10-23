package com.fallalert.app.alert

/**
 * Represents the overall system monitoring status.
 */
enum class SystemStatus {
    MONITORING,
    FALL_DETECTED
}

/**
 * Represents the connection state to the Python fall detection server.
 */
enum class NetworkStatus {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    STREAMING,
    ERROR
}

/**
 * Data class representing a recorded fall event.
 */
data class FallEvent(
    val id: String,
    val timestamp: String,
    val confidence: String,
    val description: String,
    val isSimulated: Boolean = true
)

/**
 * One-shot UI events that must be handled by MainActivity
 * (runtime permissions and placing a phone call).
 */
sealed interface EmergencyUiEvent {
    data object RequestSmsPermission : EmergencyUiEvent
    data object RequestCallPermission : EmergencyUiEvent
    data object RequestRuntimePermissions : EmergencyUiEvent
    data class PlaceCall(
        val normalizedNumber: String,
        val useDialerFallback: Boolean
    ) : EmergencyUiEvent
}

/**
 * UI State for the FallAlert application.
 */
data class FallAlertUiState(
    val systemStatus: SystemStatus = SystemStatus.MONITORING,
    val emergencyContact: String = "",
    val savedContact: String = "",
    val isAlarmActive: Boolean = false,
    val lastEvent: FallEvent? = null,
    val recentEvents: List<FallEvent> = emptyList(),
    val snackbarMessage: String? = null,

    // Real-Time Detection & Hybrid Telemetry State
    val isDetectionActive: Boolean = false,
    val serverUrl: String = "http://192.168.1.18:8002",
    val networkStatus: NetworkStatus = NetworkStatus.DISCONNECTED,
    val networkStatusMessage: String = "Detection Idle - Ready to connect",
    val currentAcceleration: Float = 9.81f,
    val modelProbability: Float = 0.0f,
    val onDeviceFallbackEnabled: Boolean = true,
    val samplesSentCount: Long = 0L,

    // SMS / emergency-call feedback (never stores a hardcoded number)
    val smsAlertStatus: SmsAlertStatus = SmsAlertStatus.IDLE,
    val smsStatusMessage: String = "SMS not sent yet",
    val lastCallStatusMessage: String = "No call placed yet",
    val isEmergencyCountdownActive: Boolean = false,
    val emergencyCountdownSeconds: Int = 0
)
