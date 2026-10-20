package com.fallalert.app.sensor

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import androidx.core.content.ContextCompat

/**
 * Reads GPS / network location for a Google Maps link in the emergency SMS.
 * Coordinates are not logged.
 */
class LocationHelper(private val context: Context) {

    private val locationManager =
        context.getSystemService(Context.LOCATION_SERVICE) as LocationManager

    @Volatile
    private var lastFix: Location? = null

    private val listener = object : LocationListener {
        override fun onLocationChanged(location: Location) {
            val previous = lastFix
            if (previous == null || location.accuracy <= previous.accuracy ||
                location.time >= previous.time
            ) {
                lastFix = location
            }
        }

        @Deprecated("Deprecated in Java")
        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit

        override fun onProviderEnabled(provider: String) = Unit
        override fun onProviderDisabled(provider: String) = Unit
    }

    fun hasLocationPermission(): Boolean {
        val fine = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
        val coarse = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
        return fine || coarse
    }

    fun startUpdates() {
        if (!hasLocationPermission()) return
        lastFix = bestLastKnown()
        try {
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER,
                    1_000L,
                    0f,
                    listener,
                    Looper.getMainLooper()
                )
            }
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER,
                    1_000L,
                    0f,
                    listener,
                    Looper.getMainLooper()
                )
            }
        } catch (_: SecurityException) {
            // Permission revoked while listening
        }
    }

    fun stopUpdates() {
        runCatching { locationManager.removeUpdates(listener) }
    }

    fun googleMapsUrl(): String? {
        val location = lastFix ?: bestLastKnown() ?: return null
        return "https://maps.google.com/?q=${location.latitude},${location.longitude}"
    }

    private fun bestLastKnown(): Location? {
        if (!hasLocationPermission()) return null
        val candidates = mutableListOf<Location>()
        try {
            locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)?.let(candidates::add)
            locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)?.let(candidates::add)
            locationManager.getLastKnownLocation(LocationManager.PASSIVE_PROVIDER)?.let(candidates::add)
        } catch (_: SecurityException) {
            return null
        }
        return candidates.maxWithOrNull(compareBy({ it.time }, { -it.accuracy }))
    }
}
