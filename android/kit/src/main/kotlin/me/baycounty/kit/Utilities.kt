package me.baycounty.kit

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.DayOfWeek
import java.time.LocalDate

/** Who provides water, sewer, power, gas and garbage at one address, and its trash pickup days. The same answer as
 *  `/api/v1/utilities` (api/_utilities.js) and the Swift `UtilityLookup`. The address isn't logged by the API, and the
 *  app doesn't cache lookups. */
@Serializable
data class UtilityLookup(
    val area: String,
    @SerialName("area_name") val areaName: String,
    val services: List<Service> = emptyList(),
    val pickup: List<Pickup> = emptyList(),
    val holidays: List<Holiday> = emptyList(),
    val rates: List<Rate> = emptyList(),
    val note: String? = null,
) {
    @Serializable
    data class Provider(
        val provider: String,
        @SerialName("entity_id") val entityId: String? = null,
        @SerialName("provider_kind") val providerKind: String? = null,
        val phone: String? = null,
        val website: String? = null,
        @SerialName("outage_url") val outageUrl: String? = null,
        val notes: String? = null,
        @SerialName("source_url") val sourceUrl: String? = null,
    )

    @Serializable
    data class Service(val service: String, @SerialName("service_label") val serviceLabel: String, val providers: List<Provider> = emptyList())

    @Serializable
    data class Pickup(
        val service: String,
        @SerialName("service_label") val serviceLabel: String,
        val provider: String,
        val zone: String? = null,
        @SerialName("zone_label") val zoneLabel: String? = null,
        val days: String? = null,
        @SerialName("zone_area") val zoneArea: String? = null,
        val rule: String? = null,
        val notes: String? = null,
        @SerialName("from_map") val fromMap: Boolean? = null,
    ) {
        /** The zone only when it adds something to the days: "route 15", "ROUTE-E", "West side". */
        val zoneText: String?
            get() {
                val z = zone ?: return null
                if (z.isEmpty() || z == days) return null
                return if (z.all { it.isDigit() }) "${zoneLabel ?: "zone"} $z" else z
            }
    }

    @Serializable
    data class Holiday(
        val provider: String? = null,
        val holiday: String,
        @SerialName("when_observed") val whenObserved: String? = null,
        val garbage: String? = null,
        @SerialName("yard_waste") val yardWaste: String? = null,
    )

    @Serializable
    data class Rate(
        val provider: String? = null,
        val service: String? = null,
        @SerialName("service_label") val serviceLabel: String? = null,
        val charge: String? = null,
        val amount: Double? = null,
        val unit: String? = null,
        val notes: String? = null,
    )

    /** The typical monthly water and sewer bill at 5,000 gallons. */
    val typicalBill: Double? get() = rates.firstOrNull { it.service == "bill" }?.amount
    /** Services with no trash-day card (garbage, yard waste and bulk providers show on their pickup card). */
    val otherServices: List<Service> get() = services.filter { s -> pickup.none { it.service == s.service } }
    fun provider(p: Pickup): Provider? = services.firstOrNull { it.service == p.service }?.providers?.firstOrNull()

    companion object {
        @Serializable
        private data class Envelope(val data: UtilityLookup)
        fun decode(json: String): UtilityLookup = BCJson.decodeFromString(Envelope.serializer(), json).data
    }
}

object PickupDays {
    private val names = listOf("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

    /** Weekdays named in "Monday, Thursday". */
    fun weekdays(days: String?): List<DayOfWeek> {
        if (days == null) return emptyList()
        return names.mapIndexedNotNull { i, n -> if (Regex("\\b$n\\b").containsMatchIn(days)) DayOfWeek.of(i + 1) else null }
    }

    /** The next date one of these weekdays comes up, today included. */
    fun next(days: String?, from: LocalDate = LocalDate.now()): LocalDate? {
        val want = weekdays(days)
        if (want.isEmpty()) return null
        return (0L..7L).map { from.plusDays(it) }.firstOrNull { it.dayOfWeek in want }
    }
}
