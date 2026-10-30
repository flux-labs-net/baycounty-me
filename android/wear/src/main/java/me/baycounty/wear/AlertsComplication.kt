package me.baycounty.wear

import android.app.PendingIntent
import android.content.Intent
import android.graphics.drawable.Icon
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.LongTextComplicationData
import androidx.wear.watchface.complications.data.MonochromaticImage
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import androidx.wear.watchface.complications.datasource.SuspendingComplicationDataSourceService
import me.baycounty.kit.WatchBrief

/** The watch face complication: the active alert count (short) or alerts plus the trash reminder (long). The watch
 *  asks again about every 15 minutes, and when the app opens or the phone sends a new home. */
class AlertsComplication : SuspendingComplicationDataSourceService() {
    override fun getPreviewData(type: ComplicationType): ComplicationData? = data(type, WatchData.demo())

    override suspend fun onComplicationRequest(request: ComplicationRequest): ComplicationData? =
        data(request.complicationType, WatchData.load(this))

    private fun text(s: String) = PlainComplicationText.Builder(s).build()

    private fun data(type: ComplicationType, b: WatchBrief.Brief): ComplicationData? {
        val tap = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val icon = MonochromaticImage.Builder(Icon.createWithResource(this, if (b.alertCount > 0) R.drawable.ic_alert else R.drawable.ic_check)).build()
        return when (type) {
            ComplicationType.SHORT_TEXT -> ShortTextComplicationData.Builder(text(b.circular), text(b.alertTitle))
                .setTitle(text("Alerts")).setMonochromaticImage(icon).setTapAction(tap).build()
            ComplicationType.LONG_TEXT -> LongTextComplicationData.Builder(text(b.alertTitle), text(b.alertTitle + ". " + b.rectangularDetail))
                .setTitle(text(b.rectangularDetail)).setMonochromaticImage(icon).setTapAction(tap).build()
            else -> null
        }
    }
}
