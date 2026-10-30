package me.baycounty.staff

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/** The site's colors (site/tokens.css), the same values as the resident app's Theme.kt. */
@Immutable
data class BrandColors(
    val navy: Color, val navyFill: Color, val salmon: Color, val salmonFill: Color, val amber: Color, val good: Color,
    val canvas: Color, val surface: Color, val sunken: Color, val hairline: Color, val text: Color, val secondary: Color, val tertiary: Color,
)

private fun rgb(r: Double, g: Double, b: Double) = Color(r.toFloat(), g.toFloat(), b.toFloat())

val LightBrand = BrandColors(
    navy = rgb(.118, .227, .463), navyFill = rgb(.118, .227, .463), salmon = rgb(.898, .337, .290), salmonFill = rgb(.761, .267, .227),
    amber = rgb(.659, .416, 0.0), good = rgb(.122, .478, .302), canvas = rgb(.965, .973, .984), surface = Color.White,
    sunken = rgb(.933, .949, .969), hairline = rgb(.890, .918, .953), text = Color(0xFF111827), secondary = Color(0xFF5B6475), tertiary = Color(0xFFA0A7B4),
)
val DarkBrand = BrandColors(
    navy = rgb(.616, .722, .918), navyFill = rgb(.227, .369, .659), salmon = rgb(1.0, .549, .510), salmonFill = rgb(.722, .243, .208),
    amber = rgb(1.0, .765, .420), good = rgb(.373, .827, .604), canvas = rgb(.043, .059, .082), surface = rgb(.102, .133, .188),
    sunken = rgb(.141, .180, .243), hairline = rgb(.173, .220, .294), text = Color(0xFFF2F4F8), secondary = Color(0xFFA6AFBE), tertiary = Color(0xFF6B7484),
)

val LocalBrand = staticCompositionLocalOf { LightBrand }
val Brand: BrandColors @Composable get() = LocalBrand.current

val Poppins = FontFamily(
    Font(R.font.poppins_regular, FontWeight.Normal), Font(R.font.poppins_medium, FontWeight.Medium),
    Font(R.font.poppins_semibold, FontWeight.SemiBold), Font(R.font.poppins_bold, FontWeight.Bold),
)
private val base = Typography()
private val typography = Typography(
    headlineMedium = base.headlineMedium.copy(fontFamily = Poppins, fontWeight = FontWeight.Bold, fontSize = 26.sp),
    headlineSmall = base.headlineSmall.copy(fontFamily = Poppins, fontWeight = FontWeight.Bold, fontSize = 22.sp, lineHeight = 28.sp),
    titleLarge = base.titleLarge.copy(fontFamily = Poppins, fontWeight = FontWeight.Bold, fontSize = 20.sp, lineHeight = 26.sp),
    titleMedium = base.titleMedium.copy(fontFamily = Poppins, fontWeight = FontWeight.SemiBold, fontSize = 16.sp),
)

object T {
    val body = TextStyle(fontSize = 16.sp, lineHeight = 22.sp)
    val bodyBold = TextStyle(fontSize = 16.sp, lineHeight = 22.sp, fontWeight = FontWeight.SemiBold)
    val subhead = TextStyle(fontSize = 15.sp, lineHeight = 20.sp)
    val footnote = TextStyle(fontSize = 13.sp, lineHeight = 18.sp)
    val caption = TextStyle(fontSize = 12.sp, lineHeight = 16.sp)
    val eyebrow = TextStyle(fontSize = 12.sp, lineHeight = 16.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 0.6.sp)
    val number = TextStyle(fontFamily = Poppins, fontWeight = FontWeight.Bold, fontSize = 24.sp, lineHeight = 30.sp)
}

@Composable
fun StaffTheme(dark: Boolean, content: @Composable () -> Unit) {
    val b = if (dark) DarkBrand else LightBrand
    val scheme = if (dark) darkColorScheme(
        primary = b.navy, onPrimary = Color.Black, secondary = b.salmon, background = b.canvas, surface = b.surface,
        onBackground = b.text, onSurface = b.text, surfaceVariant = b.sunken, onSurfaceVariant = b.secondary, outline = b.hairline,
        outlineVariant = b.hairline, surfaceContainer = b.surface, surfaceContainerHigh = b.surface, surfaceContainerLow = b.surface,
        primaryContainer = b.navyFill, onPrimaryContainer = Color.White, secondaryContainer = b.sunken,
    ) else lightColorScheme(
        primary = b.navy, onPrimary = Color.White, secondary = b.salmon, background = b.canvas, surface = b.surface,
        onBackground = b.text, onSurface = b.text, surfaceVariant = b.sunken, onSurfaceVariant = b.secondary, outline = b.hairline,
        outlineVariant = b.hairline, surfaceContainer = b.surface, surfaceContainerHigh = b.surface, surfaceContainerLow = b.surface,
        primaryContainer = b.navyFill, onPrimaryContainer = Color.White, secondaryContainer = b.sunken,
    )
    CompositionLocalProvider(LocalBrand provides b) { MaterialTheme(colorScheme = scheme, typography = typography, content = content) }
}
