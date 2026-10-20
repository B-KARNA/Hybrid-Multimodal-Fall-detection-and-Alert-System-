package com.fallalert.app.alert

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.telephony.SmsManager
import android.util.Log

/**
 * Sends a one-shot emergency SMS through the device SIM and validates
 * saved contact numbers. Call placement stays in the Activity so
 * ACTION_CALL / ACTION_DIAL can use a real foreground context.
 */
class EmergencyNotifier(private val context: Context) {

    companion object {
        const val ACTION_SMS_SENT = "com.fallalert.app.SMS_SENT"
        const val FALL_SMS_PREFIX =
            "EMERGENCY ALERT: A possible fall has been detected. Please check on the person immediately."
        const val LOCATION_UPDATE_PREFIX = "FallAlert live location update"

        /**
         * Body of the first fall SMS: alert text plus the live Google Maps link.
         */
        fun buildFallSmsBody(mapsUrl: String?): String {
            return if (!mapsUrl.isNullOrBlank()) {
                "$FALL_SMS_PREFIX\nLive location: $mapsUrl"
            } else {
                "$FALL_SMS_PREFIX\nLive location: unavailable. Turn on GPS and location permission."
            }
        }

        /**
         * Body of a follow-up SMS that refreshes the Maps link while the alarm
         * is still active, so the contact can track movement.
         */
        fun buildLocationUpdateSmsBody(sequence: Int, mapsUrl: String?): String {
            val header = "$LOCATION_UPDATE_PREFIX #$sequence"
            return if (!mapsUrl.isNullOrBlank()) {
                "$header: $mapsUrl"
            } else {
                "$header: location still unavailable. Check GPS and location permission."
            }
        }

        private const val TAG = "EmergencyNotifier"
        private const val MIN_DIGITS = 7
        private const val MAX_DIGITS = 15

        /**
         * Normalizes a user-entered phone number for SmsManager / tel: URIs.
         * Returns null when the value is blank or not a plausible phone number.
         */
        fun normalizePhoneNumber(raw: String?): String? {
            val trimmed = raw?.trim().orEmpty()
            if (trimmed.isEmpty()) return null

            val hasPlus = trimmed.startsWith("+")
            val digits = trimmed.filter { it.isDigit() }
            if (digits.length < MIN_DIGITS || digits.length > MAX_DIGITS) {
                return null
            }
            return if (hasPlus) "+$digits" else digits
        }

        fun isValidPhoneNumber(raw: String?): Boolean = normalizePhoneNumber(raw) != null
    }

    /**
     * Queues an SMS on the default SIM. Delivery status is reported via
     * [ACTION_SMS_SENT] so the Activity can map SmsManager result codes.
     * Pass a [locationUpdateSequence] greater than 0 to send a follow-up
     * live-location refresh instead of the initial fall alert.
     */
    fun sendFallSms(
        rawNumber: String,
        mapsUrl: String? = null,
        locationUpdateSequence: Int = 0
    ): SmsDispatchResult {
        val number = normalizePhoneNumber(rawNumber)
            ?: return SmsDispatchResult.InvalidNumber
        val body = if (locationUpdateSequence > 0) {
            buildLocationUpdateSmsBody(locationUpdateSequence, mapsUrl)
        } else {
            buildFallSmsBody(mapsUrl)
        }

        return try {
            val smsManager = resolveSmsManager()
                ?: return SmsDispatchResult.Failed("SMS service is unavailable on this device")

            val sentIntent = Intent(ACTION_SMS_SENT).apply {
                setPackage(context.packageName)
            }
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            val parts = smsManager.divideMessage(body)
            val sentIntents = java.util.ArrayList<PendingIntent>(parts.size)
            for (index in 0 until parts.size) {
                sentIntents.add(
                    PendingIntent.getBroadcast(
                        context,
                        index,
                        sentIntent,
                        flags
                    )
                )
            }

            if (parts.size <= 1) {
                smsManager.sendTextMessage(
                    number,
                    null,
                    body,
                    sentIntents.firstOrNull(),
                    null
                )
            } else {
                smsManager.sendMultipartTextMessage(
                    number,
                    null,
                    parts,
                    sentIntents,
                    null
                )
            }
            Log.d(TAG, "Emergency SMS queued on default SIM")
            SmsDispatchResult.Queued
        } catch (security: SecurityException) {
            Log.e(TAG, "SMS permission missing or revoked", security)
            SmsDispatchResult.PermissionDenied
        } catch (error: Exception) {
            Log.e(TAG, "Failed to send emergency SMS: ${error.message}", error)
            SmsDispatchResult.Failed(error.message ?: "Unknown SMS error")
        }
    }

    private fun resolveSmsManager(): SmsManager? {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            context.getSystemService(SmsManager::class.java)
        } else {
            @Suppress("DEPRECATION")
            SmsManager.getDefault()
        }
    }
}

sealed class SmsDispatchResult {
    data object Queued : SmsDispatchResult()
    data object InvalidNumber : SmsDispatchResult()
    data object PermissionDenied : SmsDispatchResult()
    data class Failed(val reason: String) : SmsDispatchResult()
}

enum class SmsAlertStatus {
    IDLE,
    SENDING,
    SENT,
    FAILED,
    PERMISSION_DENIED
}
