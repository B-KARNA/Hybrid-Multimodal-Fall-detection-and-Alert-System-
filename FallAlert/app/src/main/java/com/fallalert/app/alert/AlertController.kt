package com.fallalert.app.alert

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log

/**
 * AlertController manages repeating audio alarm playback and vibration feedback.
 * Designed to be lifecycle-aware and leak-free.
 */
class AlertController(private val context: Context) {

    private val tag = "AlertController"
    private var mediaPlayer: MediaPlayer? = null
    private var isPlayingAudio = false
    private var isVibrating = false

    private val vibrator: Vibrator by lazy {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vibratorManager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            vibratorManager.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }
    }

    /**
     * Starts both repeating alarm sound and pulsing vibration pattern.
     */
    @Synchronized
    fun startAlert() {
        Log.d(tag, "Starting emergency alarm and vibration...")
        startAudioAlarm()
        startVibration()
    }

    /**
     * Immediately stops audio alarm and vibration.
     */
    @Synchronized
    fun stopAlert() {
        Log.d(tag, "Stopping emergency alarm and vibration...")
        stopAudioAlarm()
        stopVibration()
    }

    private fun startAudioAlarm() {
        if (isPlayingAudio) return

        try {
            // Find appropriate emergency alarm sound or fallback to ringtone/notification
            var alertUri: Uri? = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            if (alertUri == null) {
                alertUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
            }
            if (alertUri == null) {
                alertUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            }

            mediaPlayer?.release()
            mediaPlayer = MediaPlayer().apply {
                setDataSource(context, alertUri!!)
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .setLegacyStreamType(AudioManager.STREAM_ALARM)
                        .build()
                )
                isLooping = true
                prepare()
                start()
            }
            isPlayingAudio = true
        } catch (e: Exception) {
            Log.e(tag, "Failed to start audio alarm: ${e.message}", e)
        }
    }

    private fun stopAudioAlarm() {
        try {
            mediaPlayer?.let { player ->
                if (player.isPlaying) {
                    player.stop()
                }
                player.release()
            }
        } catch (e: Exception) {
            Log.e(tag, "Error stopping audio alarm: ${e.message}", e)
        } finally {
            mediaPlayer = null
            isPlayingAudio = false
        }
    }

    private fun startVibration() {
        if (isVibrating) return

        try {
            if (vibrator.hasVibrator()) {
                // High-urgency pulse pattern: 0ms delay, 600ms vibrate, 300ms pause, 600ms vibrate, 600ms pause
                val pattern = longArrayOf(0, 600, 300, 600, 600)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    val effect = VibrationEffect.createWaveform(pattern, 0) // 0 means repeat indefinitely
                    vibrator.vibrate(effect)
                } else {
                    @Suppress("DEPRECATION")
                    vibrator.vibrate(pattern, 0)
                }
                isVibrating = true
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to start vibration: ${e.message}", e)
        }
    }

    private fun stopVibration() {
        try {
            if (isVibrating) {
                vibrator.cancel()
            }
        } catch (e: Exception) {
            Log.e(tag, "Error cancelling vibration: ${e.message}", e)
        } finally {
            isVibrating = false
        }
    }

    /**
     * Clean up all hardware resources when app finishes.
     */
    fun release() {
        stopAlert()
    }
}
