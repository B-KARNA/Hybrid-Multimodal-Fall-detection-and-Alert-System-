package com.fallalert.app.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Alarm
import androidx.compose.material.icons.filled.AlarmOff
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Sensors
import androidx.compose.material.icons.filled.Sms
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fallalert.app.alert.FallAlertUiState
import com.fallalert.app.alert.FallEvent
import com.fallalert.app.alert.NetworkStatus
import com.fallalert.app.alert.SmsAlertStatus
import com.fallalert.app.alert.SystemStatus
import com.fallalert.app.ui.FallAlertViewModel
import com.fallalert.app.ui.theme.AccentAmber
import com.fallalert.app.ui.theme.AccentBlue
import com.fallalert.app.ui.theme.AlertRedPrimary
import com.fallalert.app.ui.theme.SafeGreenPrimary
import com.fallalert.app.ui.theme.SurfaceBorder
import com.fallalert.app.ui.theme.SurfaceDarkCard
import com.fallalert.app.ui.theme.SurfaceInput
import com.fallalert.app.ui.theme.TextMuted
import com.fallalert.app.ui.theme.TextPrimary
import com.fallalert.app.ui.theme.TextSecondary
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    uiState: FallAlertUiState,
    viewModel: FallAlertViewModel,
    modifier: Modifier = Modifier
) {
    val snackbarHostState = remember { SnackbarHostState() }
    val focusManager = LocalFocusManager.current

    LaunchedEffect(uiState.snackbarMessage) {
        uiState.snackbarMessage?.let { msg ->
            snackbarHostState.showSnackbar(
                message = msg,
                duration = SnackbarDuration.Short
            )
            viewModel.dismissMessage()
        }
    }

    Scaffold(
        modifier = modifier.fillMaxSize(),
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Surface(
                            shape = CircleShape,
                            color = when {
                                uiState.isAlarmActive -> AlertRedPrimary
                                uiState.isDetectionActive -> SafeGreenPrimary
                                else -> TextMuted
                            },
                            modifier = Modifier.size(12.dp)
                        ) {}
                        Text(
                            text = "FallAlert",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                    }
                },
                actions = {
                    StatusBadge(
                        isAlarm = uiState.isAlarmActive,
                        isDetecting = uiState.isDetectionActive
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = SurfaceDarkCard
                )
            )
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            contentPadding = PaddingValues(vertical = 16.dp)
        ) {
            // 1. System Status Hero Card
            item {
                SystemStatusHeroCard(
                    status = uiState.systemStatus,
                    isAlarmActive = uiState.isAlarmActive,
                    isDetecting = uiState.isDetectionActive,
                    countdownSeconds = uiState.emergencyCountdownSeconds,
                    countdownActive = uiState.isEmergencyCountdownActive
                )
            }

            // 2. Real-Time Fall Detection System Card
            item {
                DetectionSystemCard(
                    uiState = uiState,
                    onStartDetection = {
                        focusManager.clearFocus()
                        viewModel.startDetection()
                    },
                    onStopDetection = {
                        viewModel.stopDetection()
                    },
                    onServerUrlChange = viewModel::onServerUrlChange,
                    onSaveServerUrl = {
                        focusManager.clearFocus()
                        viewModel.saveServerUrl()
                    },
                    onTestConnection = {
                        focusManager.clearFocus()
                        viewModel.testServerConnection()
                    },
                    onToggleFallback = viewModel::toggleOnDeviceFallback
                )
            }

            // 3. Emergency Alarm Controls Card
            item {
                AlarmControlsCard(
                    isAlarmActive = uiState.isAlarmActive,
                    onTestAlarm = {
                        focusManager.clearFocus()
                        viewModel.triggerAlarm(isTest = true)
                    },
                    onStopAlarm = {
                        viewModel.stopAlarm()
                    },
                    onCallContact = {
                        viewModel.initiateEmergencyCall(isManualTest = true)
                    },
                    countdownActive = uiState.isEmergencyCountdownActive,
                    countdownSeconds = uiState.emergencyCountdownSeconds
                )
            }

            // 4. Emergency Contact Card
            item {
                EmergencyContactCard(
                    contact = uiState.emergencyContact,
                    savedContact = uiState.savedContact,
                    smsStatusMessage = uiState.smsStatusMessage,
                    smsAlertStatus = uiState.smsAlertStatus,
                    callStatusMessage = uiState.lastCallStatusMessage,
                    onContactChange = viewModel::onEmergencyContactChange,
                    onSaveContact = {
                        focusManager.clearFocus()
                        viewModel.saveEmergencyContact()
                    },
                    onTestSms = {
                        focusManager.clearFocus()
                        viewModel.sendFallSms(isManualTest = true)
                    },
                    onTestCall = {
                        focusManager.clearFocus()
                        viewModel.initiateEmergencyCall(isManualTest = true)
                    }
                )
            }

            // 5. Fall Event Status Area
            item {
                AlertStatusArea(
                    lastEvent = uiState.lastEvent
                )
            }

            // 6. Recent Events Activity Log
            if (uiState.recentEvents.isNotEmpty()) {
                item {
                    Text(
                        text = "Recent Events Activity",
                        style = MaterialTheme.typography.titleMedium,
                        color = TextPrimary,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(top = 8.dp, bottom = 4.dp)
                    )
                }

                items(uiState.recentEvents) { event ->
                    EventHistoryItem(event = event)
                }
            }
        }
    }
}

/**
 * Top App Bar status chip
 */
@Composable
fun StatusBadge(isAlarm: Boolean, isDetecting: Boolean) {
    val (bg, text, color) = when {
        isAlarm -> Triple(AlertRedPrimary.copy(alpha = 0.2f), "ALARM ACTIVE", AlertRedPrimary)
        isDetecting -> Triple(SafeGreenPrimary.copy(alpha = 0.2f), "DETECTING LIVE", SafeGreenPrimary)
        else -> Triple(SurfaceInput, "STANDBY", TextSecondary)
    }

    Surface(
        shape = RoundedCornerShape(20.dp),
        color = bg,
        border = BorderStroke(1.dp, color.copy(alpha = 0.6f)),
        modifier = Modifier.padding(end = 12.dp)
    ) {
        Text(
            text = text,
            color = color,
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
        )
    }
}

/**
 * Hero card indicating System Status
 */
@Composable
fun SystemStatusHeroCard(
    status: SystemStatus,
    isAlarmActive: Boolean,
    isDetecting: Boolean,
    countdownSeconds: Int = 0,
    countdownActive: Boolean = false
) {
    val isEmergency = status == SystemStatus.FALL_DETECTED || isAlarmActive

    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = if (isEmergency) 1.08f else 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(600),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseScale"
    )

    val cardBorderColor by animateColorAsState(
        targetValue = when {
            isEmergency -> AlertRedPrimary
            isDetecting -> SafeGreenPrimary.copy(alpha = 0.7f)
            else -> SurfaceBorder
        },
        label = "borderColor"
    )

    val cardBackgroundBrush = when {
        isEmergency -> Brush.verticalGradient(listOf(Color(0xFF450A0A), SurfaceDarkCard))
        isDetecting -> Brush.verticalGradient(listOf(Color(0xFF063024), SurfaceDarkCard))
        else -> Brush.verticalGradient(listOf(Color(0xFF131A29), SurfaceDarkCard))
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(BorderStroke(1.5.dp, cardBorderColor), RoundedCornerShape(18.dp)),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = Color.Transparent)
    ) {
        Box(
            modifier = Modifier
                .background(cardBackgroundBrush)
                .padding(20.dp)
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.fillMaxWidth()
            ) {
                Box(
                    modifier = Modifier
                        .scale(pulseScale)
                        .size(64.dp)
                        .clip(CircleShape)
                        .background(
                            when {
                                isEmergency -> AlertRedPrimary.copy(alpha = 0.25f)
                                isDetecting -> SafeGreenPrimary.copy(alpha = 0.2f)
                                else -> SurfaceInput
                            }
                        )
                        .border(
                            BorderStroke(
                                2.dp,
                                when {
                                    isEmergency -> AlertRedPrimary
                                    isDetecting -> SafeGreenPrimary
                                    else -> TextMuted
                                }
                            ),
                            CircleShape
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = when {
                            isEmergency -> Icons.Default.Warning
                            isDetecting -> Icons.Default.Sensors
                            else -> Icons.Default.Security
                        },
                        contentDescription = "Status Indicator",
                        tint = when {
                            isEmergency -> AlertRedPrimary
                            isDetecting -> SafeGreenPrimary
                            else -> TextSecondary
                        },
                        modifier = Modifier.size(34.dp)
                    )
                }

                Spacer(modifier = Modifier.height(14.dp))

                Text(
                    text = when {
                        isEmergency -> "EMERGENCY: FALL DETECTED!"
                        isDetecting -> "SYSTEM STATUS: ACTIVE MONITORING"
                        else -> "SYSTEM STATUS: ARMED & READY"
                    },
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.ExtraBold,
                    color = when {
                        isEmergency -> AlertRedPrimary
                        isDetecting -> SafeGreenPrimary
                        else -> TextPrimary
                    }
                )

                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = when {
                        countdownActive ->
                            "False alarm window: SMS and auto-call in ${countdownSeconds}s. Press Stop Alarm now to cancel."
                        isEmergency ->
                            "Repeating alarm active. SMS and call were dispatched to the saved contact."
                        isDetecting ->
                            "Streaming accelerometer, gravity & gyroscope to Python model. On-device fallback active."
                        else ->
                            "Detection system is ready. Tap Test Connection, then Start Fall Detection."
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary,
                    modifier = Modifier.padding(horizontal = 8.dp),
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center
                )
            }
        }
    }
}

/**
 * Real-Time Detection System Control & Telemetry Card
 */
@Composable
fun DetectionSystemCard(
    uiState: FallAlertUiState,
    onStartDetection: () -> Unit,
    onStopDetection: () -> Unit,
    onServerUrlChange: (String) -> Unit,
    onSaveServerUrl: () -> Unit,
    onTestConnection: () -> Unit,
    onToggleFallback: (Boolean) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDarkCard),
        border = BorderStroke(1.dp, SurfaceBorder)
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Sensors,
                    contentDescription = "Detection System",
                    tint = AccentBlue,
                    modifier = Modifier.size(22.dp)
                )
                Text(
                    text = "Fall Detection Engine",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
            }

            Text(
                text = "Streams 9-channel sensors to Python model + listens for PC camera alerts",
                style = MaterialTheme.typography.bodySmall,
                color = TextMuted,
                modifier = Modifier.padding(top = 2.dp)
            )

            Spacer(modifier = Modifier.height(14.dp))

            // Main Start / Stop Detection Button
            if (!uiState.isDetectionActive) {
                Button(
                    onClick = onStartDetection,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = SafeGreenPrimary,
                        contentColor = Color.Black
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.PlayArrow,
                        contentDescription = "Start Detection",
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Start Fall Detection",
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
            } else {
                OutlinedButton(
                    onClick = onStopDetection,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                    shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.5.dp, AlertRedPrimary),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = AlertRedPrimary
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.Stop,
                        contentDescription = "Stop Detection",
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Stop Detection & Sensor Streaming",
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Python Server Connection URL Input
            OutlinedTextField(
                value = uiState.serverUrl,
                onValueChange = onServerUrlChange,
                label = { Text("Alert Manager URL", fontSize = 12.sp) },
                placeholder = { Text("http://192.168.1.18:8002") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Done
                ),
                keyboardActions = KeyboardActions(
                    onDone = { onSaveServerUrl() }
                ),
                trailingIcon = {
                    Button(
                        onClick = onSaveServerUrl,
                        shape = RoundedCornerShape(8.dp),
                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = AccentBlue),
                        modifier = Modifier.padding(end = 4.dp)
                    ) {
                        Text("Save", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    }
                },
                shape = RoundedCornerShape(10.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = AccentBlue,
                    unfocusedBorderColor = SurfaceBorder,
                    focusedContainerColor = SurfaceInput,
                    unfocusedContainerColor = SurfaceInput,
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary
                )
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "Address of the centralized Alert Manager on your PC (not this phone). Use the PC's Wi-Fi IPv4 address, not 0.0.0.0. Example: http://192.168.1.18:8002",
                style = MaterialTheme.typography.bodySmall,
                color = TextMuted
            )

            Spacer(modifier = Modifier.height(8.dp))

            OutlinedButton(
                onClick = onTestConnection,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(44.dp),
                shape = RoundedCornerShape(12.dp),
                border = BorderStroke(1.5.dp, AccentBlue),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentBlue)
            ) {
                Text("Test Connection to Python Model", fontWeight = FontWeight.Bold, fontSize = 13.sp)
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Live Network Connection Pill
            Surface(
                shape = RoundedCornerShape(10.dp),
                color = SurfaceInput,
                border = BorderStroke(1.dp, SurfaceBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Icon(
                        imageVector = when (uiState.networkStatus) {
                            NetworkStatus.STREAMING, NetworkStatus.CONNECTED -> Icons.Default.Wifi
                            NetworkStatus.CONNECTING -> Icons.Default.Bolt
                            else -> Icons.Default.WifiOff
                        },
                        contentDescription = "Network Status",
                        tint = when (uiState.networkStatus) {
                            NetworkStatus.STREAMING -> SafeGreenPrimary
                            NetworkStatus.CONNECTED -> SafeGreenPrimary
                            NetworkStatus.CONNECTING -> AccentAmber
                            NetworkStatus.ERROR -> AccentAmber
                            NetworkStatus.DISCONNECTED -> TextMuted
                        },
                        modifier = Modifier.size(18.dp)
                    )

                    Text(
                        text = uiState.networkStatusMessage,
                        style = MaterialTheme.typography.bodySmall,
                        color = when (uiState.networkStatus) {
                            NetworkStatus.STREAMING -> SafeGreenPrimary
                            NetworkStatus.CONNECTED -> SafeGreenPrimary
                            NetworkStatus.ERROR -> AccentAmber
                            else -> TextSecondary
                        },
                        fontWeight = FontWeight.Medium
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Live Telemetry Row (Acceleration & Model Probability)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // Telemetry 1: Real-Time Acceleration
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = SurfaceInput,
                    border = BorderStroke(1.dp, SurfaceBorder),
                    modifier = Modifier.weight(1f)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Speed,
                                contentDescription = "Acceleration",
                                tint = AccentBlue,
                                modifier = Modifier.size(14.dp)
                            )
                            Text(
                                text = "Motion Acceleration",
                                style = MaterialTheme.typography.labelSmall,
                                color = TextMuted
                            )
                        }

                        Spacer(modifier = Modifier.height(4.dp))

                        val formattedAcc = String.format(Locale.getDefault(), "%.2f", uiState.currentAcceleration)
                        Text(
                            text = "$formattedAcc m/s²",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = when {
                                uiState.currentAcceleration > 20f -> AlertRedPrimary
                                uiState.currentAcceleration < 4f -> AccentAmber
                                else -> TextPrimary
                            }
                        )

                        Spacer(modifier = Modifier.height(4.dp))

                        val accProgress = (uiState.currentAcceleration / 30f).coerceIn(0f, 1f)
                        LinearProgressIndicator(
                            progress = { accProgress },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(4.dp)
                                .clip(RoundedCornerShape(2.dp)),
                            color = AccentBlue,
                            trackColor = SurfaceBorder
                        )
                    }
                }

                // Telemetry 2: Model Fall Probability
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = SurfaceInput,
                    border = BorderStroke(1.dp, SurfaceBorder),
                    modifier = Modifier.weight(1f)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Bolt,
                                contentDescription = "Model",
                                tint = AccentAmber,
                                modifier = Modifier.size(14.dp)
                            )
                            Text(
                                text = "Model Probability",
                                style = MaterialTheme.typography.labelSmall,
                                color = TextMuted
                            )
                        }

                        Spacer(modifier = Modifier.height(4.dp))

                        val probPercent = (uiState.modelProbability * 100).toInt()
                        Text(
                            text = "$probPercent%",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = when {
                                probPercent >= 40 -> AlertRedPrimary
                                probPercent >= 20 -> AccentAmber
                                else -> SafeGreenPrimary
                            }
                        )

                        Spacer(modifier = Modifier.height(4.dp))

                        LinearProgressIndicator(
                            progress = { uiState.modelProbability.coerceIn(0f, 1f) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(4.dp)
                                .clip(RoundedCornerShape(2.dp)),
                            color = if (probPercent >= 40) AlertRedPrimary else AccentAmber,
                            trackColor = SurfaceBorder
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // On-Device Fallback Switch
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(SurfaceInput, RoundedCornerShape(10.dp))
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "On-Device Inertial Fallback",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = TextPrimary
                    )
                    Text(
                        text = "Detects free-fall & impact locally if Wi-Fi disconnects",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMuted
                    )
                }

                Switch(
                    checked = uiState.onDeviceFallbackEnabled,
                    onCheckedChange = onToggleFallback,
                    colors = SwitchDefaults.colors(
                        checkedThumbColor = SafeGreenPrimary,
                        checkedTrackColor = SafeGreenPrimary.copy(alpha = 0.3f),
                        uncheckedThumbColor = TextMuted,
                        uncheckedTrackColor = SurfaceBorder
                    )
                )
            }
        }
    }
}

/**
 * Emergency Alarm Controls (Test Alarm & Stop Alarm)
 */
@Composable
fun AlarmControlsCard(
    isAlarmActive: Boolean,
    onTestAlarm: () -> Unit,
    onStopAlarm: () -> Unit,
    onCallContact: () -> Unit,
    countdownActive: Boolean = false,
    countdownSeconds: Int = 0
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDarkCard),
        border = BorderStroke(1.dp, SurfaceBorder)
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Text(
                text = "Alarm & Sound Controls",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Text(
                text = if (countdownActive) {
                    "Stop Alarm in ${countdownSeconds}s to cancel automatic SMS and call"
                } else {
                    "Test Alarm starts sound now, then auto SMS + call after 20 seconds unless you stop it"
                },
                style = MaterialTheme.typography.bodySmall,
                color = if (countdownActive) AlertRedPrimary else TextMuted
            )

            Spacer(modifier = Modifier.height(16.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = onTestAlarm,
                    modifier = Modifier
                        .weight(1f)
                        .height(52.dp),
                    shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.5.dp, AccentAmber),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = AccentAmber
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.NotificationsActive,
                        contentDescription = "Test Alarm",
                        tint = AccentAmber,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Test Alarm",
                        fontWeight = FontWeight.Bold,
                        fontSize = 14.sp
                    )
                }

                Button(
                    onClick = onStopAlarm,
                    enabled = isAlarmActive,
                    modifier = Modifier
                        .weight(1f)
                        .height(52.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = AlertRedPrimary,
                        contentColor = Color.White,
                        disabledContainerColor = SurfaceInput,
                        disabledContentColor = TextMuted
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.AlarmOff,
                        contentDescription = "Stop Alarm",
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Stop Alarm",
                        fontWeight = FontWeight.Bold,
                        fontSize = 14.sp
                    )
                }
            }

            AnimatedVisibility(visible = isAlarmActive) {
                Column {
                    Spacer(modifier = Modifier.height(12.dp))
                    Button(
                        onClick = onCallContact,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = AccentBlue,
                            contentColor = Color.White
                        )
                    ) {
                        Icon(
                            imageVector = Icons.Default.Call,
                            contentDescription = "Call emergency contact",
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Call Saved Contact",
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp
                        )
                    }
                    Text(
                        text = "After the 8-second cancel window the app sends the SMS automatically and " +
                            "places the call to the saved contact without any tap. The SMS carries a live " +
                            "Google Maps link that keeps refreshing while the alarm stays active.",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMuted,
                        modifier = Modifier.padding(top = 6.dp)
                    )
                }
            }
        }
    }
}

/**
 * Emergency Contact configuration card
 */
@Composable
fun EmergencyContactCard(
    contact: String,
    savedContact: String,
    smsStatusMessage: String,
    smsAlertStatus: SmsAlertStatus,
    callStatusMessage: String,
    onContactChange: (String) -> Unit,
    onSaveContact: () -> Unit,
    onTestSms: () -> Unit,
    onTestCall: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDarkCard),
        border = BorderStroke(1.dp, SurfaceBorder)
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Phone,
                    contentDescription = "Emergency Phone",
                    tint = SafeGreenPrimary,
                    modifier = Modifier.size(20.dp)
                )
                Text(
                    text = "Emergency Contact Number",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = "Saved locally on this phone. Used only for Test SMS, Test Call, and real fall alerts.",
                style = MaterialTheme.typography.bodySmall,
                color = TextMuted
            )

            Spacer(modifier = Modifier.height(14.dp))

            OutlinedTextField(
                value = contact,
                onValueChange = onContactChange,
                modifier = Modifier.fillMaxWidth(),
                placeholder = {
                    Text(
                        text = "e.g. +1 555-019-2834 or 9876543210",
                        color = TextMuted,
                        fontSize = 14.sp
                    )
                },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Phone,
                    imeAction = ImeAction.Done
                ),
                keyboardActions = KeyboardActions(
                    onDone = { onSaveContact() }
                ),
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = SafeGreenPrimary,
                    unfocusedBorderColor = SurfaceBorder,
                    focusedContainerColor = SurfaceInput,
                    unfocusedContainerColor = SurfaceInput,
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary
                )
            )

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (savedContact.isNotBlank()) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = "Saved",
                            tint = SafeGreenPrimary,
                            modifier = Modifier.size(16.dp)
                        )
                        Text(
                            text = "Saved: $savedContact",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary,
                            fontWeight = FontWeight.Medium
                        )
                    }
                } else {
                    Text(
                        text = "No contact saved yet",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMuted
                    )
                }

                Button(
                    onClick = onSaveContact,
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = SafeGreenPrimary,
                        contentColor = Color.Black
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.Save,
                        contentDescription = "Save",
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Save Contact",
                        fontWeight = FontWeight.Bold,
                        fontSize = 13.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = onTestSms,
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.5.dp, AccentBlue),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = AccentBlue)
                ) {
                    Icon(
                        imageVector = Icons.Default.Sms,
                        contentDescription = "Test SMS",
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Test SMS", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }

                OutlinedButton(
                    onClick = onTestCall,
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.5.dp, SafeGreenPrimary),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = SafeGreenPrimary)
                ) {
                    Icon(
                        imageVector = Icons.Default.Call,
                        contentDescription = "Test Call",
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Test Call", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            val smsColor = when (smsAlertStatus) {
                SmsAlertStatus.SENT -> SafeGreenPrimary
                SmsAlertStatus.FAILED, SmsAlertStatus.PERMISSION_DENIED -> AlertRedPrimary
                SmsAlertStatus.SENDING -> AccentAmber
                SmsAlertStatus.IDLE -> TextMuted
            }

            Text(
                text = "SMS: $smsStatusMessage",
                style = MaterialTheme.typography.bodySmall,
                color = smsColor
            )
            Text(
                text = "Call: $callStatusMessage",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary,
                modifier = Modifier.padding(top = 4.dp)
            )
            Text(
                text = "Live location: every emergency SMS includes a Google Maps link, refreshed while the alarm is active.",
                style = MaterialTheme.typography.bodySmall,
                color = TextMuted,
                modifier = Modifier.padding(top = 4.dp)
            )
        }
    }
}

/**
 * Alert Status Area showing received fall event details
 */
@Composable
fun AlertStatusArea(
    lastEvent: FallEvent?
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceDarkCard),
        border = BorderStroke(1.dp, SurfaceBorder)
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Alarm,
                    contentDescription = "Alert Details",
                    tint = TextPrimary,
                    modifier = Modifier.size(20.dp)
                )
                Text(
                    text = "Fall Event Status Area",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            if (lastEvent != null) {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = SurfaceInput,
                    border = BorderStroke(1.dp, SurfaceBorder),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = "Event ID: #${lastEvent.id}",
                                style = MaterialTheme.typography.labelLarge,
                                color = SafeGreenPrimary
                            )
                            Text(
                                text = lastEvent.timestamp,
                                style = MaterialTheme.typography.bodySmall,
                                color = TextMuted
                            )
                        }

                        Spacer(modifier = Modifier.height(6.dp))

                        Text(
                            text = "Confidence: ${lastEvent.confidence}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextPrimary,
                            fontWeight = FontWeight.SemiBold
                        )

                        Spacer(modifier = Modifier.height(4.dp))

                        Text(
                            text = lastEvent.description,
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                }
            } else {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = SurfaceInput,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "No fall events recorded yet. Start detection or press 'Test Alarm' to simulate an alert.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextMuted,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center
                        )
                    }
                }
            }
        }
    }
}

/**
 * Event history list item
 */
@Composable
fun EventHistoryItem(event: FallEvent) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = SurfaceDarkCard,
        border = BorderStroke(1.dp, SurfaceBorder),
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Surface(
                shape = CircleShape,
                color = AlertRedPrimary.copy(alpha = 0.2f),
                modifier = Modifier.size(32.dp)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = "Event",
                        tint = AlertRedPrimary,
                        modifier = Modifier.size(16.dp)
                    )
                }
            }

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = event.description,
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextPrimary,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = "${event.timestamp} • ${event.confidence}",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMuted
                )
            }
        }
    }
}
