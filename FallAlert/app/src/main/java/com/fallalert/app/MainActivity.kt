package com.fallalert.app

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import com.fallalert.app.alert.EmergencyNotifier
import com.fallalert.app.alert.EmergencyUiEvent
import com.fallalert.app.ui.FallAlertViewModel
import com.fallalert.app.ui.screens.HomeScreen
import com.fallalert.app.ui.theme.FallAlertTheme

class MainActivity : ComponentActivity() {

    private val viewModel: FallAlertViewModel by viewModels()

    private val runtimePermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        viewModel.onRuntimePermissionsResult(grants)
    }

    private val smsPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        viewModel.onSmsPermissionResult(granted)
    }

    private val callPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        viewModel.onCallPermissionResult(granted)
    }

    private val smsSentReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == EmergencyNotifier.ACTION_SMS_SENT) {
                viewModel.onSmsSendResult(resultCode)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestMissingRuntimePermissions()

        setContent {
            FallAlertTheme {
                Surface(
                    modifier = Modifier.fillMaxSize()
                ) {
                    val uiState by viewModel.uiState.collectAsState()

                    LaunchedEffect(Unit) {
                        viewModel.emergencyEvents.collect { event ->
                            handleEmergencyEvent(event)
                        }
                    }

                    HomeScreen(
                        uiState = uiState,
                        viewModel = viewModel
                    )
                }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        val filter = IntentFilter(EmergencyNotifier.ACTION_SMS_SENT)
        ContextCompat.registerReceiver(
            this,
            smsSentReceiver,
            filter,
            ContextCompat.RECEIVER_NOT_EXPORTED
        )
    }

    override fun onStop() {
        super.onStop()
        runCatching { unregisterReceiver(smsSentReceiver) }
    }

    private fun handleEmergencyEvent(event: EmergencyUiEvent) {
        when (event) {
            EmergencyUiEvent.RequestSmsPermission -> {
                smsPermissionLauncher.launch(Manifest.permission.SEND_SMS)
            }
            EmergencyUiEvent.RequestCallPermission -> {
                callPermissionLauncher.launch(Manifest.permission.CALL_PHONE)
            }
            EmergencyUiEvent.RequestRuntimePermissions -> {
                requestMissingRuntimePermissions()
            }
            is EmergencyUiEvent.PlaceCall -> {
                placeCall(event.normalizedNumber, event.useDialerFallback)
            }
        }
    }

    private fun placeCall(normalizedNumber: String, useDialerFallback: Boolean) {
        val canDirectCall = !useDialerFallback &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE) ==
            PackageManager.PERMISSION_GRANTED

        val action = if (canDirectCall) Intent.ACTION_CALL else Intent.ACTION_DIAL
        val intent = Intent(action).apply {
            data = Uri.fromParts("tel", normalizedNumber, null)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }

        try {
            startActivity(intent)
            viewModel.onCallIntentLaunched(
                usedDialerFallback = action == Intent.ACTION_DIAL,
                success = true
            )
        } catch (missing: ActivityNotFoundException) {
            viewModel.onCallIntentLaunched(
                usedDialerFallback = true,
                success = false,
                error = "No phone app is available to place this call"
            )
        } catch (error: SecurityException) {
            if (action == Intent.ACTION_CALL) {
                placeCall(normalizedNumber, useDialerFallback = true)
            } else {
                viewModel.onCallIntentLaunched(
                    usedDialerFallback = true,
                    success = false,
                    error = "Unable to open the dialer"
                )
            }
        }
    }

    private fun requestMissingRuntimePermissions() {
        val needed = mutableListOf<String>()
        val candidates = mutableListOf(
            Manifest.permission.SEND_SMS,
            Manifest.permission.CALL_PHONE,
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            candidates.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        for (permission in candidates) {
            if (ContextCompat.checkSelfPermission(this, permission) != PackageManager.PERMISSION_GRANTED) {
                needed.add(permission)
            }
        }
        if (needed.isNotEmpty()) {
            runtimePermissionLauncher.launch(needed.toTypedArray())
        }
    }
}
