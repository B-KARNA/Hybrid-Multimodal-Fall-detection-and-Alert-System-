package com.fallalert.app.ui

import android.Manifest
import android.app.Activity
import android.app.Application
import android.content.pm.PackageManager
import android.telephony.SmsManager
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.fallalert.app.alert.AlertController
import com.fallalert.app.alert.EmergencyNotifier
import com.fallalert.app.alert.EmergencyUiEvent
import com.fallalert.app.alert.FallAlertUiState
import com.fallalert.app.alert.FallEvent
import com.fallalert.app.alert.NetworkStatus
import com.fallalert.app.alert.SmsAlertStatus
import com.fallalert.app.alert.SmsDispatchResult
import com.fallalert.app.alert.SystemStatus
import com.fallalert.app.data.ContactRepository
import com.fallalert.app.sensor.DetectionNetworkClient
import com.fallalert.app.sensor.LocationHelper
import com.fallalert.app.sensor.SensorCollector
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

/**
 * FallAlertViewModel coordinates domain state, emergency alarms, hardware sensor
 * streaming, and real-time Python model network communication.
 */
class FallAlertViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = ContactRepository(application)
    private val alertController = AlertController(application)
    private val emergencyNotifier = EmergencyNotifier(application)
    private val sensorCollector = SensorCollector(application)
    private val locationHelper = LocationHelper(application)
    private val networkClient = DetectionNetworkClient()

    private val _uiState = MutableStateFlow(FallAlertUiState())
    val uiState: StateFlow<FallAlertUiState> = _uiState.asStateFlow()

    private val _emergencyEvents = MutableSharedFlow<EmergencyUiEvent>(extraBufferCapacity = 16)
    val emergencyEvents: SharedFlow<EmergencyUiEvent> = _emergencyEvents.asSharedFlow()

    private var statusPollingJob: Job? = null
    private var streamingSendJob: Job? = null
    private var emergencyDispatchJob: Job? = null
    private var locationUpdateJob: Job? = null

    // One SMS / one auto-call per fall event (consecutive FALL labels ignored)
    private var smsSentForCurrentEvent: Boolean = false
    private var callPlacedForCurrentEvent: Boolean = false
    private var pendingSmsIsTest: Boolean = false
    private var pendingCallIsTest: Boolean = false

    // Describes which SMS the pending delivery callback belongs to.
    private var pendingSmsStatusLabel: String = "saved emergency contact"

    // Buffer that lets the user cancel a false alarm before alerts are dispatched.
    // Extended to 20 seconds so the user has comfortable time to cancel false alarms.
    private val falseAlarmCancelWindowSeconds = 20

    // Live location follow-up SMS cadence while the alarm stays active.
    private val locationUpdateIntervalMs = 60_000L
    private val maxLocationUpdates = 5

    init {
        // Load stored configuration on startup
        val savedContact = repository.getEmergencyContact()
        val savedServerUrl = repository.getServerUrl()
        val fallbackEnabled = repository.isOnDeviceFallbackEnabled()

        sensorCollector.onDeviceFallbackEnabled = fallbackEnabled

        _uiState.update {
            it.copy(
                emergencyContact = savedContact,
                savedContact = savedContact,
                serverUrl = savedServerUrl,
                onDeviceFallbackEnabled = fallbackEnabled
            )
        }
    }

    /**
     * Starts the full hybrid detection system:
     * 1. Hardware sensors (accel, gravity, gyro) sampling and streaming.
     * 2. On-device freefall & impact fallback detector.
     * 3. Python backend polling for vision/camera alerts.
     */
    fun startDetection() {
        if (_uiState.value.isDetectionActive) return

        val serverUrl = _uiState.value.serverUrl.trim()
        _emergencyEvents.tryEmit(EmergencyUiEvent.RequestRuntimePermissions)

        _uiState.update {
            it.copy(
                isDetectionActive = true,
                networkStatus = NetworkStatus.CONNECTING,
                networkStatusMessage = "Starting sensors & connecting to $serverUrl..."
            )
        }
        locationHelper.startUpdates()
        testServerConnection(showSnackbar = false)

        // Start hardware sensor sampling & streaming
        sensorCollector.start(
            onTelemetry = { magnitude ->
                _uiState.update { it.copy(currentAcceleration = magnitude) }
            },
            onBatchReady = { jsonBatch ->
                dispatchSensorBatch(jsonBatch)
            },
            onLocalFallDetected = { confidence, description ->
                triggerAlarm(
                    isTest = false,
                    customConfidence = confidence,
                    customDescription = description
                )
            }
        )

        // Start periodic status poller (checks vision/camera fall alerts)
        startStatusPoller(serverUrl)
    }

    /**
     * Stops detection and releases sensors.
     */
    fun stopDetection() {
        sensorCollector.stop()
        statusPollingJob?.cancel()
        statusPollingJob = null
        locationHelper.stopUpdates()

        _uiState.update {
            it.copy(
                isDetectionActive = false,
                networkStatus = NetworkStatus.DISCONNECTED,
                networkStatusMessage = "Detection stopped. Sensors paused."
            )
        }
    }

    private fun dispatchSensorBatch(jsonBatch: String) {
        val serverUrl = _uiState.value.serverUrl
        if (streamingSendJob?.isActive == true) {
            // Drop backpressure frame if previous is still transmitting
            return
        }

        streamingSendJob = viewModelScope.launch {
            val result = networkClient.sendSensorBatch(serverUrl, jsonBatch)
            if (result.success) {
                _uiState.update { current ->
                    current.copy(
                        networkStatus = NetworkStatus.STREAMING,
                        networkStatusMessage = "Streaming sensors to PC • ${result.samplesCount} buffer",
                        modelProbability = result.probability,
                        samplesSentCount = current.samplesSentCount + 1
                    )
                }

                // If Python LSTM model reports a fall!
                if (result.fallDetected) {
                    val percent = String.format(Locale.getDefault(), "%.1f", result.probability * 100)
                    triggerAlarm(
                        isTest = false,
                        customConfidence = "$percent% (Python LSTM Sensor Model)",
                        customDescription = "Python model predicted fall from continuous smartphone movement"
                    )
                }
            } else {
                // Server is unreachable, on-device fallback keeps protecting user
                _uiState.update { current ->
                    current.copy(
                        networkStatus = NetworkStatus.ERROR,
                        networkStatusMessage = "PC offline (${result.errorMessage?.take(25)}...) • On-device fallback ACTIVE"
                    )
                }
            }
        }
    }

    private fun startStatusPoller(serverUrl: String) {
        statusPollingJob?.cancel()
        statusPollingJob = viewModelScope.launch {
            while (isActive) {
                delay(1600L) // Poll every 1.6s
                val result = networkClient.checkServerStatus(serverUrl)
                if (result.success) {
                    _uiState.update { current ->
                        current.copy(
                            networkStatus = if (current.networkStatus == NetworkStatus.STREAMING) current.networkStatus else NetworkStatus.CONNECTED,
                            modelProbability = if (result.probability > 0f) result.probability else current.modelProbability
                        )
                    }

                    if (result.fallDetected) {
                        val percent = String.format(Locale.getDefault(), "%.1f", result.probability * 100)
                        triggerAlarm(
                            isTest = false,
                            customConfidence = "$percent% (Python Vision Camera Alert)",
                            customDescription = "Emergency: Fall detected by indoor video camera pipeline!"
                        )
                    }
                }
            }
        }
    }

    /**
     * Updates the server URL string input.
     */
    fun onServerUrlChange(newUrl: String) {
        _uiState.update { it.copy(serverUrl = newUrl) }
    }

    /**
     * Persists the server URL.
     */
    fun saveServerUrl() {
        val url = _uiState.value.serverUrl.trim()
        if (url.isBlank()) {
            _uiState.update { it.copy(snackbarMessage = "Please enter a valid server URL") }
            return
        }
        val saved = repository.saveServerUrl(url)
        if (saved) {
            _uiState.update { it.copy(snackbarMessage = "Server URL saved: $url") }
        }
    }

    /**
     * Toggles on-device impact/freefall detection fallback.
     */
    fun toggleOnDeviceFallback(enabled: Boolean) {
        sensorCollector.onDeviceFallbackEnabled = enabled
        repository.setOnDeviceFallbackEnabled(enabled)
        _uiState.update { it.copy(onDeviceFallbackEnabled = enabled) }
    }

    /**
     * Updates the emergency contact text input.
     */
    fun onEmergencyContactChange(newContact: String) {
        _uiState.update { it.copy(emergencyContact = newContact) }
    }

    /**
     * Saves the current contact string to persistent storage.
     */
    fun saveEmergencyContact() {
        val contactToSave = _uiState.value.emergencyContact.trim()
        if (!EmergencyNotifier.isValidPhoneNumber(contactToSave)) {
            _uiState.update {
                it.copy(snackbarMessage = "Enter a valid phone number (7–15 digits, optional + country code)")
            }
            return
        }

        val success = repository.saveEmergencyContact(contactToSave)
        if (success) {
            _uiState.update {
                it.copy(
                    savedContact = contactToSave,
                    snackbarMessage = "Emergency contact saved successfully"
                )
            }
        } else {
            _uiState.update { it.copy(snackbarMessage = "Failed to save contact") }
        }
    }

    private var lastAlarmTriggerTime: Long = 0L
    private val alarmCooldownMs: Long = 12_000L // 12-second cooldown between distinct fall events

    /**
     * Triggers a fall detection alarm event with de-bouncing protection.
     */
    fun triggerAlarm(
        isTest: Boolean = true,
        customConfidence: String? = null,
        customDescription: String? = null
    ) {
        val nowMs = System.currentTimeMillis()

        // 1. Do not trigger or duplicate if alarm is already active!
        if (_uiState.value.isAlarmActive) {
            return
        }

        // 2. Enforce cooldown to prevent multiple alerts for a single physical fall event
        if (!isTest && (nowMs - lastAlarmTriggerTime < alarmCooldownMs)) {
            return
        }
        lastAlarmTriggerTime = nowMs

        val now = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
        val event = FallEvent(
            id = UUID.randomUUID().toString().take(8),
            timestamp = now,
            confidence = customConfidence ?: if (isTest) "99.8% (Manual Simulation)" else "96.4% (Live Model)",
            description = customDescription ?: if (isTest) "Manual Test Alarm triggered by user" else "Rapid acceleration & posture change detected",
            isSimulated = isTest
        )

        // Start repeating alarm sound and pulsing vibration immediately
        alertController.startAlert()

        smsSentForCurrentEvent = false
        callPlacedForCurrentEvent = false
        // Permissions are requested on startup and when detection starts, never
        // during the emergency itself, so alerts go out without any dialog.
        locationHelper.startUpdates()

        val missingPermissions = missingEmergencyPermissions()
        val windowMessage = if (missingPermissions.isEmpty()) {
            "Alarm on. Press Stop Alarm within ${falseAlarmCancelWindowSeconds}s to cancel SMS and call."
        } else {
            "Alarm on. Grant ${missingPermissions.joinToString(" & ")} permission for fully automatic alerts. " +
                "Press Stop Alarm within ${falseAlarmCancelWindowSeconds}s to cancel."
        }

        _uiState.update { current ->
            current.copy(
                systemStatus = SystemStatus.FALL_DETECTED,
                isAlarmActive = true,
                lastEvent = event,
                recentEvents = listOf(event) + current.recentEvents.take(9),
                isEmergencyCountdownActive = true,
                emergencyCountdownSeconds = falseAlarmCancelWindowSeconds,
                snackbarMessage = windowMessage
            )
        }

        startEmergencyDispatchCountdown()
    }

    /**
     * Silences repeating alarm sound and stops vibration, restoring armed status.
     */
    fun stopAlarm() {
        val cancelledDispatch = emergencyDispatchJob?.isActive == true
        emergencyDispatchJob?.cancel()
        emergencyDispatchJob = null
        // Stop ongoing live-location follow-up SMS as soon as the alarm is silenced.
        locationUpdateJob?.cancel()
        locationUpdateJob = null
        alertController.stopAlert()
        // Prevent lingering network packets from re-triggering immediately
        lastAlarmTriggerTime = System.currentTimeMillis()

        _uiState.update { current ->
            current.copy(
                systemStatus = SystemStatus.MONITORING,
                isAlarmActive = false,
                isEmergencyCountdownActive = false,
                emergencyCountdownSeconds = 0,
                snackbarMessage = if (cancelledDispatch) {
                    "False alarm cancelled. SMS and call were not sent."
                } else {
                    "Alarm silenced. System re-armed and monitoring."
                }
            )
        }
    }

    /**
     * Pings GET /status so the user can verify the phone can reach the PC model.
     */
    fun testServerConnection(showSnackbar: Boolean = true) {
        val serverUrl = _uiState.value.serverUrl.trim()
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    networkStatus = NetworkStatus.CONNECTING,
                    networkStatusMessage = "Testing connection to $serverUrl ..."
                )
            }
            val result = networkClient.checkServerStatus(serverUrl)
            if (result.success) {
                _uiState.update {
                    it.copy(
                        networkStatus = NetworkStatus.CONNECTED,
                        networkStatusMessage = "Python model reachable at $serverUrl",
                        modelProbability = result.probability,
                        snackbarMessage = if (showSnackbar) "Connected to the Python fall model" else it.snackbarMessage
                    )
                }
            } else {
                val detail = result.errorMessage ?: "timeout / unreachable"
                _uiState.update {
                    it.copy(
                        networkStatus = NetworkStatus.ERROR,
                        networkStatusMessage = "Cannot reach PC: $detail",
                        snackbarMessage = if (showSnackbar) {
                            "Cannot reach the Alert Manager. Use this PC's Wi-Fi IPv4 address (not 0.0.0.0), keep the Alert Manager and detectors running, and allow port 8002 in Windows Firewall."
                        } else {
                            it.snackbarMessage
                        }
                    )
                }
            }
        }
    }

    private fun startEmergencyDispatchCountdown() {
        emergencyDispatchJob?.cancel()
        emergencyDispatchJob = viewModelScope.launch {
            for (remaining in falseAlarmCancelWindowSeconds downTo 1) {
                if (!isActive) return@launch
                _uiState.update {
                    it.copy(
                        isEmergencyCountdownActive = true,
                        emergencyCountdownSeconds = remaining
                    )
                }
                delay(1_000L)
            }

            _uiState.update {
                it.copy(
                    isEmergencyCountdownActive = false,
                    emergencyCountdownSeconds = 0
                )
            }

            sendFallSms(isManualTest = false)
            initiateEmergencyCall(isManualTest = false)
            startLocationUpdateLoop()
        }
    }

    /**
     * While the alarm stays active, re-sends the live Google Maps link every
     * [locationUpdateIntervalMs] so the saved contact can follow movement.
     * Stops automatically when the user cancels the alarm.
     */
    private fun startLocationUpdateLoop() {
        locationUpdateJob?.cancel()
        locationUpdateJob = viewModelScope.launch {
            for (sequence in 1..maxLocationUpdates) {
                delay(locationUpdateIntervalMs)
                if (!isActive || !_uiState.value.isAlarmActive) return@launch
                if (!hasPermission(Manifest.permission.SEND_SMS)) return@launch

                val savedNumber = repository.getEmergencyContact()
                if (!EmergencyNotifier.isValidPhoneNumber(savedNumber)) return@launch

                dispatchSms(
                    savedNumber = savedNumber,
                    isManualTest = false,
                    locationUpdateSequence = sequence
                )
            }
        }
    }

    /**
     * Sends the fall SMS to the saved emergency contact via the device SIM.
     * [isManualTest] bypasses the per-event duplicate guard so Test SMS stays independent.
     */
    fun sendFallSms(isManualTest: Boolean = true) {
        val savedNumber = repository.getEmergencyContact()
        if (!EmergencyNotifier.isValidPhoneNumber(savedNumber)) {
            _uiState.update {
                it.copy(
                    smsAlertStatus = SmsAlertStatus.FAILED,
                    smsStatusMessage = "Cannot send SMS: save a valid emergency contact first",
                    snackbarMessage = "Save a valid emergency contact number before sending SMS"
                )
            }
            return
        }

        if (!isManualTest && smsSentForCurrentEvent) {
            _uiState.update {
                it.copy(
                    snackbarMessage = "SMS already sent for this fall event"
                )
            }
            return
        }

        if (!hasPermission(Manifest.permission.SEND_SMS)) {
            if (isManualTest) {
                pendingSmsIsTest = true
                _uiState.update {
                    it.copy(
                        smsAlertStatus = SmsAlertStatus.IDLE,
                        smsStatusMessage = "Waiting for SMS permission…"
                    )
                }
                _emergencyEvents.tryEmit(EmergencyUiEvent.RequestSmsPermission)
                return
            }
            // Real emergency: never block on a permission dialog. Report and continue
            // so the automatic call can still be placed.
            _uiState.update {
                it.copy(
                    smsAlertStatus = SmsAlertStatus.PERMISSION_DENIED,
                    smsStatusMessage = "Emergency SMS not sent: SEND_SMS permission is not granted",
                    snackbarMessage = "Emergency SMS blocked. Enable SMS permission in Settings for automatic alerts."
                )
            }
            return
        }

        dispatchSms(savedNumber, isManualTest)
    }

    fun onRuntimePermissionsResult(grants: Map<String, Boolean>) {
        val locationOk = grants[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            grants[Manifest.permission.ACCESS_COARSE_LOCATION] == true ||
            hasPermission(Manifest.permission.ACCESS_FINE_LOCATION) ||
            hasPermission(Manifest.permission.ACCESS_COARSE_LOCATION)
        if (locationOk) {
            locationHelper.startUpdates()
        }
    }

    fun onSmsPermissionResult(granted: Boolean) {
        if (granted) {
            sendFallSms(isManualTest = pendingSmsIsTest)
            return
        }
        _uiState.update {
            it.copy(
                smsAlertStatus = SmsAlertStatus.PERMISSION_DENIED,
                smsStatusMessage = "SMS permission denied. Enable SEND_SMS in system settings to send alerts.",
                snackbarMessage = "SMS permission denied. Emergency SMS was not sent."
            )
        }
    }

    fun onSmsSendResult(resultCode: Int) {
        val (status, message) = when (resultCode) {
            Activity.RESULT_OK -> SmsAlertStatus.SENT to "SMS sent to $pendingSmsStatusLabel"
            SmsManager.RESULT_ERROR_NO_SERVICE ->
                SmsAlertStatus.FAILED to "SMS failed: no cellular service"
            SmsManager.RESULT_ERROR_RADIO_OFF ->
                SmsAlertStatus.FAILED to "SMS failed: radio/airplane mode is off"
            SmsManager.RESULT_ERROR_NULL_PDU ->
                SmsAlertStatus.FAILED to "SMS failed: invalid message PDU"
            SmsManager.RESULT_ERROR_GENERIC_FAILURE ->
                SmsAlertStatus.FAILED to "SMS failed: generic telephony error"
            else -> SmsAlertStatus.FAILED to "SMS failed (code $resultCode)"
        }
        _uiState.update {
            it.copy(
                smsAlertStatus = status,
                smsStatusMessage = message,
                snackbarMessage = message
            )
        }
    }

    /**
     * Starts a user-confirmed call to the saved contact.
     * Uses ACTION_CALL when CALL_PHONE is granted; otherwise requests it and
     * falls back to ACTION_DIAL so the user can still place the call.
     */
    fun initiateEmergencyCall(isManualTest: Boolean = true) {
        val normalized = EmergencyNotifier.normalizePhoneNumber(repository.getEmergencyContact())
        if (normalized == null) {
            _uiState.update {
                it.copy(
                    lastCallStatusMessage = "Cannot call: save a valid emergency contact first",
                    snackbarMessage = "Save a valid emergency contact number before calling"
                )
            }
            return
        }

        if (!isManualTest && callPlacedForCurrentEvent) {
            _uiState.update {
                it.copy(
                    snackbarMessage = "A call was already started for this fall event"
                )
            }
            return
        }

        pendingCallIsTest = isManualTest

        if (hasPermission(Manifest.permission.CALL_PHONE)) {
            startCall(normalized, useDialerFallback = false, isManualTest = isManualTest)
            return
        }

        if (isManualTest) {
            // User tapped Test Call, so asking for the permission here is expected.
            _uiState.update {
                it.copy(lastCallStatusMessage = "Waiting for call permission…")
            }
            _emergencyEvents.tryEmit(EmergencyUiEvent.RequestCallPermission)
            return
        }

        // Real emergency: no dialogs. CALL_PHONE is required for a truly hands-free
        // call, so fall back to the pre-filled dialer as a last resort.
        _uiState.update {
            it.copy(
                lastCallStatusMessage = "Call permission is not granted. Opening the dialer (one tap needed). " +
                    "Grant Phone permission in Settings for fully automatic calls.",
                snackbarMessage = "Auto-call needs Phone permission. Opening the dialer instead."
            )
        }
        startCall(normalized, useDialerFallback = true, isManualTest = false)
    }

    fun onCallPermissionResult(granted: Boolean) {
        val normalized = EmergencyNotifier.normalizePhoneNumber(repository.getEmergencyContact())
        if (normalized == null) {
            _uiState.update {
                it.copy(
                    lastCallStatusMessage = "Cannot call: save a valid emergency contact first",
                    snackbarMessage = "Save a valid emergency contact number before calling"
                )
            }
            return
        }

        if (granted) {
            startCall(normalized, useDialerFallback = false, isManualTest = pendingCallIsTest)
            return
        }

        _uiState.update {
            it.copy(
                lastCallStatusMessage = "Call permission denied. Opening the dialer instead.",
                snackbarMessage = "Call permission denied. Opening the dialer so you can place the call."
            )
        }
        startCall(normalized, useDialerFallback = true, isManualTest = pendingCallIsTest)
    }

    fun onCallIntentLaunched(usedDialerFallback: Boolean, success: Boolean, error: String? = null) {
        val message = when {
            !success -> error ?: "Unable to start a phone call on this device"
            usedDialerFallback -> "Dialer opened with the saved contact. Confirm the call in the phone app."
            else -> "Calling saved emergency contact…"
        }
        _uiState.update {
            it.copy(
                lastCallStatusMessage = message,
                snackbarMessage = message
            )
        }
    }

    private fun dispatchSms(
        savedNumber: String,
        isManualTest: Boolean,
        locationUpdateSequence: Int = 0
    ) {
        val isLocationUpdate = locationUpdateSequence > 0
        pendingSmsStatusLabel = if (isLocationUpdate) {
            "saved emergency contact (live location update #$locationUpdateSequence)"
        } else {
            "saved emergency contact"
        }

        _uiState.update {
            it.copy(
                smsAlertStatus = SmsAlertStatus.SENDING,
                smsStatusMessage = if (isLocationUpdate) {
                    "Sending live location update #$locationUpdateSequence via device SIM…"
                } else {
                    "Sending emergency SMS via device SIM…"
                }
            )
        }

        when (
            val result = emergencyNotifier.sendFallSms(
                rawNumber = savedNumber,
                mapsUrl = locationHelper.googleMapsUrl(),
                locationUpdateSequence = locationUpdateSequence
            )
        ) {
            SmsDispatchResult.Queued -> {
                if (!isManualTest) {
                    smsSentForCurrentEvent = true
                }
                _uiState.update {
                    it.copy(
                        smsAlertStatus = SmsAlertStatus.SENDING,
                        smsStatusMessage = if (isLocationUpdate) {
                            "Live location update #$locationUpdateSequence queued."
                        } else {
                            "SMS queued. Waiting for the cellular network…"
                        },
                        snackbarMessage = if (isLocationUpdate) {
                            "Live location update #$locationUpdateSequence queued"
                        } else {
                            "Emergency SMS queued to the saved contact"
                        }
                    )
                }
            }
            SmsDispatchResult.InvalidNumber -> {
                _uiState.update {
                    it.copy(
                        smsAlertStatus = SmsAlertStatus.FAILED,
                        smsStatusMessage = "Cannot send SMS: saved number is not valid",
                        snackbarMessage = "Saved phone number is not valid"
                    )
                }
            }
            SmsDispatchResult.PermissionDenied -> {
                _uiState.update {
                    it.copy(
                        smsAlertStatus = SmsAlertStatus.PERMISSION_DENIED,
                        smsStatusMessage = "SMS permission denied",
                        snackbarMessage = "SMS permission denied. Emergency SMS was not sent."
                    )
                }
            }
            is SmsDispatchResult.Failed -> {
                _uiState.update {
                    it.copy(
                        smsAlertStatus = SmsAlertStatus.FAILED,
                        smsStatusMessage = "SMS failed: ${result.reason}",
                        snackbarMessage = "SMS failed: ${result.reason}"
                    )
                }
            }
        }
    }

    private fun startCall(normalizedNumber: String, useDialerFallback: Boolean, isManualTest: Boolean) {
        if (!isManualTest) {
            callPlacedForCurrentEvent = true
        }
        _emergencyEvents.tryEmit(
            EmergencyUiEvent.PlaceCall(
                normalizedNumber = normalizedNumber,
                useDialerFallback = useDialerFallback
            )
        )
    }

    private fun hasPermission(permission: String): Boolean {
        return ContextCompat.checkSelfPermission(
            getApplication(),
            permission
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * Human-readable names of the permissions required for a hands-free
     * emergency SMS + call. Used to warn the user before an emergency happens.
     */
    private fun missingEmergencyPermissions(): List<String> {
        val missing = mutableListOf<String>()
        if (!hasPermission(Manifest.permission.SEND_SMS)) missing.add("SMS")
        if (!hasPermission(Manifest.permission.CALL_PHONE)) missing.add("Phone")
        return missing
    }

    /**
     * Dismisses the transient snackbar message.
     */
    fun dismissMessage() {
        _uiState.update { it.copy(snackbarMessage = null) }
    }

    override fun onCleared() {
        super.onCleared()
        sensorCollector.stop()
        statusPollingJob?.cancel()
        emergencyDispatchJob?.cancel()
        locationUpdateJob?.cancel()
        locationHelper.stopUpdates()
        alertController.release()
    }
}
