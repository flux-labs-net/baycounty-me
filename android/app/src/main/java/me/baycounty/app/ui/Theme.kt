package me.baycounty.app.ui

import androidx.compose.foundation.isSystemInDarkTheme
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
import me.baycounty.app.R

/** Colors from the site's tokens (site/tokens.css), with the same dark-mode values as the iOS asset catalog. */
@Immutable
data class BrandColors(
    val navy: Color,
    val navyFill: Color,
    val blue: Color,
    val salmon: Color,
    val salmonFill: Color,
    val amber: Color,
    val good: Color,
    val canvas: Color,
    val surface: Color,
    val sunken: Color,
    val hairline: Color,
    val text: Color,
    val secondary: Color,
    val tertiary: Color,
    val dark: Boolean,
)

private fun rgb(r: Double, g: Double, b: Double) = Color(r.toFloat(), g.toFloat(), b.toFloat())

val LightBrand = BrandColors(
    navy = rgb(.118, .227, .463), navyFill = rgb(.118, .227, .463), blue = rgb(.247, .435, .690),
    salmon = rgb(.898, .337, .290), salmonFill = rgb(.761, .267, .227), amber = rgb(.659, .416, 0.0),
    good = rgb(.122, .478, .302), canvas = rgb(.965, .973, .984), surface = Color.White,
    sunken = rgb(.933, .949, .969), hairline = rgb(.890, .918, .953),
    text = Color(0xFF111827), secondary = Color(0xFF5B6475), tertiary = Color(0xFFA0A7B4), dark = false,
)

val DarkBrand = BrandColors(
    navy = rgb(.616, .722, .918), navyFill = rgb(.227, .369, .659), blue = rgb(.498, .651, .855),
    salmon = rgb(1.0, .549, .510), salmonFill = rgb(.722, .243, .208), amber = rgb(1.0, .765, .420),
    good = rgb(.373, .827, .604), canvas = rgb(.043, .059, .082), surface = rgb(.102, .133, .188),
    sunken = rgb(.141, .180, .243), hairline = rgb(.173, .220, .294),
    text = Color(0xFFF2F4F8), secondary = Color(0xFFA6AFBE), tertiary = Color(0xFF6B7484), dark = true,
)

val LocalBrand = staticCompositionLocalOf { LightBrand }

/** The current palette: `Brand.navy` etc. inside composables. */
val Brand: BrandColors @Composable get() = LocalBrand.current

/** Poppins for headings, 700 for titles (never 800), 600 for small headings. */
val Poppins = FontFamily(
    Font(R.font.poppins_regular, FontWeight.Normal),
    Font(R.font.poppins_medium, FontWeight.Medium),
    Font(R.font.poppins_semibold, FontWeight.SemiBold),
    Font(R.font.poppins_bold, FontWeight.Bold),
)

private val base = Typography()
val AppTypography = Typography(
    displaySmall = base.displaySmall.copy(fontFamily = Poppins, fontWeight = FontWeight.Bold),
    headlineLarge = base.headlineLarge.copy(fontFamily = Poppins, fontWeight = FontWeight.Bold),
    headlineMedium = base.headlineMedium.copy(fontFamily = Poppins, fontWeight = FontWeight.Bold, fontSize = 26.sp),
    headlineSmall = base.headlineSmall.copy(fontFamily = Poppins, fontWeight = FontWeight.Bold, fontSize = 22.sp, lineHeight = 28.sp),
    titleLarge = base.titleLarge.copy(fontFamily = Poppins, fontWeight = FontWeight.Bold, fontSize = 20.sp, lineHeight = 26.sp),
    titleMedium = base.titleMedium.copy(fontFamily = Poppins, fontWeight = FontWeight.SemiBold, fontSize = 16.sp),
    titleSmall = base.titleSmall.copy(fontFamily = Poppins, fontWeight = FontWeight.SemiBold),
)

/** Shorthand text styles used across screens (body text stays in the system font). */
object T {
    val title2 @Composable get() = MaterialTheme.typography.headlineSmall
    val title3 @Composable get() = MaterialTheme.typography.titleLarge
    val headline @Composable get() = MaterialTheme.typography.titleMedium
    val body = TextStyle(fontSize = 16.sp, lineHeight = 22.sp)
    val subhead = TextStyle(fontSize = 15.sp, lineHeight = 20.sp)
    val subheadBold = TextStyle(fontSize = 15.sp, lineHeight = 20.sp, fontWeight = FontWeight.SemiBold)
    val footnote = TextStyle(fontSize = 13.sp, lineHeight = 18.sp)
    val caption = TextStyle(fontSize = 12.sp, lineHeight = 16.sp)
    val caption2 = TextStyle(fontSize = 11.sp, lineHeight = 14.sp)
    val number = TextStyle(fontFamily = Poppins, fontWeight = FontWeight.Bold, fontSize = 20.sp, lineHeight = 26.sp)
    val bigNumber = TextStyle(fontFamily = Poppins, fontWeight = FontWeight.Bold, fontSize = 26.sp, lineHeight = 32.sp)
}

@Composable
fun BayCountyTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val b = if (dark) DarkBrand else LightBrand
    val scheme = if (dark) darkColorScheme(
        primary = b.navy, onPrimary = Color.Black, secondary = b.salmon, background = b.canvas, surface = b.surface,
        onBackground = b.text, onSurface = b.text, surfaceVariant = b.sunken, onSurfaceVariant = b.secondary,
        outline = b.hairline, outlineVariant = b.hairline, surfaceContainer = b.surface, surfaceContainerHigh = b.surface,
        surfaceContainerLow = b.surface, primaryContainer = b.navyFill, onPrimaryContainer = Color.White,
    ) else lightColorScheme(
        primary = b.navy, onPrimary = Color.White, secondary = b.salmon, background = b.canvas, surface = b.surface,
        onBackground = b.text, onSurface = b.text, surfaceVariant = b.sunken, onSurfaceVariant = b.secondary,
        outline = b.hairline, outlineVariant = b.hairline, surfaceContainer = b.surface, surfaceContainerHigh = b.surface,
        surfaceContainerLow = b.surface, primaryContainer = b.navyFill, onPrimaryContainer = Color.White,
    )
    CompositionLocalProvider(LocalBrand provides b) {
        MaterialTheme(colorScheme = scheme, typography = AppTypography, content = content)
    }
}

/** Matches the CRA Spending page: Spent green, Committed blue, Budgeted amber, Proposed salmon. */
@Composable
fun statusColor(s: String): Color = when (s) {
    "Spent" -> Brand.good
    "Committed" -> Brand.blue
    "Budgeted" -> Brand.amber
    "Proposed" -> Brand.salmon
    else -> Brand.secondary
}

/** Group colors, matching the website's --s1...--s5 series. */
@Composable
fun taxColor(group: String): Color = when (group) {
    "school" -> Brand.navy
    "county" -> Brand.blue
    "city" -> Brand.salmon
    "countysvc" -> Brand.amber
    else -> Brand.good
}

/** The four tones the site gives its icons and badges. */
enum class Tone { BLUE, TEAL, AMBER, SALMON }

@Composable
fun Tone.color(): Color = when (this) {
    Tone.BLUE -> Brand.navy
    Tone.TEAL -> Brand.good
    Tone.AMBER -> Brand.amber
    Tone.SALMON -> Brand.salmon
}
