package com.fallalert.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val FallAlertColorScheme = darkColorScheme(
    primary = SafeGreenPrimary,
    onPrimary = Color.Black,
    primaryContainer = SafeGreenContainer,
    onPrimaryContainer = SafeGreenOnContainer,
    secondary = AccentBlue,
    onSecondary = Color.White,
    error = AlertRedPrimary,
    onError = Color.White,
    errorContainer = AlertRedContainer,
    onErrorContainer = AlertRedOnContainer,
    background = MidnightDarkBackground,
    onBackground = TextPrimary,
    surface = SurfaceDarkCard,
    onSurface = TextPrimary,
    surfaceVariant = SurfaceInput,
    onSurfaceVariant = TextSecondary,
    outline = SurfaceBorder
)

@Composable
fun FallAlertTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = FallAlertColorScheme,
        typography = Typography,
        content = content
    )
}
