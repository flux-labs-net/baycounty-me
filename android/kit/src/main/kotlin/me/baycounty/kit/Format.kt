package me.baycounty.kit

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.text.NumberFormat
import java.time.Instant
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

object Format {
    private val us = Locale.US

    private fun currency(fraction: Int): NumberFormat = NumberFormat.getCurrencyInstance(us).apply {
        minimumFractionDigits = fraction; maximumFractionDigits = fraction
    }

    private val plain: ThreadLocal<DecimalFormat> = ThreadLocal.withInitial {
        DecimalFormat("#,##0.####", DecimalFormatSymbols(us))
    }

    /** $1,234,567 (cents kept under $1,000 so per-resident and fee figures stay exact). */
    fun money(value: Double?): String {
        value ?: return "Not stated"
        val cents = Math.abs(value) < 1000 && value != Math.rint(value)
        return currency(if (cents) 2 else 0).format(value)
    }

    /** $1.2M, $340K, $950. */
    fun compactMoney(value: Double): String {
        val a = Math.abs(value)
        val sign = if (value < 0) "-" else ""
        fun trim(x: Double): String {
            val s = String.format(us, if (x >= 100) "%.0f" else "%.1f", x)
            return if (s.endsWith(".0")) s.dropLast(2) else s
        }
        return when {
            a >= 1e9 -> "$sign\$${trim(a / 1e9)}B"
            a >= 1e6 -> "$sign\$${trim(a / 1e6)}M"
            a >= 1e4 -> "$sign\$${trim(a / 1e3)}K"
            else -> money(value)
        }
    }

    fun number(value: Double): String = plain.get().format(value)
    fun number(value: Int): String = number(value.toDouble())

    private val labelOverrides = mapOf(
        "cra" to "CRA", "gov" to "Government", "fy" to "Fiscal year", "date_or_fy" to "When", "count" to "Counted in totals",
        "pct_complete" to "Percent complete", "pct_of_original" to "Percent of original", "fema_michael_obligated" to "FEMA (Hurricane Michael)",
        "population_2025" to "Population (2025)", "population_2025_estimate" to "Population (2025)", "employees_fte" to "Employees (full-time equivalent)",
        "budgeted_fte" to "Budgeted positions (FTE)", "n_contributions" to "Contributions", "tally" to "Vote", "split" to "Split vote",
        "residential_single_family_amount" to "Typical home pays", "per_resident" to "Per resident", "rolled_back_rate" to "Rolled-back rate",
        "location_name" to "Location", "plain_english" to "In plain English", "voted_yes" to "Voted yes", "voted_no" to "Voted no",
        "absent_or_abstained" to "Absent or abstained", "par_amount" to "Amount borrowed", "applies_to" to "Applies to",
        "first_obligated" to "First approved", "last_obligated" to "Last approved", "own_money" to "Own money", "url" to "Link",
    )

    /** "date_or_fy" -> "When", "total_raised" -> "Total raised". */
    fun label(column: String): String {
        labelOverrides[column]?.let { return it }
        val s = column.split("_").joinToString(" ") { w ->
            when (w.lowercase()) {
                "fy" -> "FY"; "fema" -> "FEMA"; "cra" -> "CRA"; "id" -> "ID"; "pct" -> "%"
                else -> w
            }
        }
        return s.capitalizeFirst()
    }

    private val moneyWords = listOf("amount", "cost", "total", "budget", "levy", "fund", "debt", "salary", "annual", "raised",
        "spent", "share", "outstanding", "value", "per_resident", "eligible", "obligated", "bill",
        "pay_min", "pay_mid", "pay_max", "hourly", "removed", "own_money", "from_organizations", "par")
    private val notMoneyWords = listOf("pct", "count", "n_", "payments", "parcels", "homesteads", "population", "residents",
        "fte", "millage", "rate", "votes", "findings", "year", "contributions", "note", "status",
        "as_of", "level", "line", "schedule_fy")

    fun isMoneyColumn(column: String): Boolean {
        val c = column.lowercase()
        if (notMoneyWords.any { c.contains(it) }) return false
        return moneyWords.any { c.contains(it) }
    }

    /** Readable text for a value in a given column. */
    fun value(v: JsonElement, column: String): String = when (v) {
        is JsonNull -> ""
        is JsonPrimitive -> when {
            v.isString -> stringValue(v.content, column)
            v.booleanOrNull != null -> if (v.booleanOrNull == true) "Yes" else "No"
            else -> {
                val n = v.doubleValue ?: 0.0
                when {
                    isMoneyColumn(column) -> money(n)
                    column.startsWith("pct") -> "${number(n)}%"
                    column.contains("year") || column == "fy" -> n.toLong().toString()
                    else -> number(n)
                }
            }
        }
        is JsonArray -> v.map { value(it, column) }.filter { it.isNotEmpty() }
            .joinToString(if (column == "actual_salaries") ", " else "\n")
        is JsonObject -> v.entries.sortedBy { it.key }.joinToString(", ") { "${it.key}: ${value(it.value, column)}" }
    }

    private fun stringValue(s: String, column: String): String {
        if (s == "True" || s == "False") return if (s == "True") "Yes" else "No"
        val d = Dates.parse(s)
        if (d != null && s.length in 10..25) return Dates.display(d, hasTime = s.length > 10)
        if (column in listOf("government", "gov", "employer", "gov_id")) Governments.names[s]?.let { return it }
        return humanizeCode(s, column)
    }

    private val codeColumns = setOf("status", "race_status", "kind", "level", "category", "outcome", "vote", "type", "contributor_type", "pay_status")
    private val codeRe = Regex("^[a-z0-9_]+$")

    /** Snake-case status codes like "in_progress" read as "In progress". */
    fun humanizeCode(s: String, column: String): String {
        if (column !in codeColumns || !codeRe.matches(s)) return s
        return s.replace("_", " ").capitalizeFirst()
    }

    // ---- Organization names in normal case ----

    /** Words kept in capitals when an ALL-CAPS organization name is recased. */
    private val keepUpper = setOf(
        "USA", "US", "U.S.", "VFW", "YMCA", "YWCA", "PTA", "PTO", "PTSA", "HOA", "FL", "FSU", "UWF", "FAMU", "UF", "NAACP", "AMVETS",
        "LLC", "LLLP", "LP", "PA", "PC", "PLLC", "II", "III", "IV", "VI", "PCB", "NW", "NE", "SW", "SE", "ARC", "CDC", "CRA", "DBA",
        "AARP", "NAMI", "ROTC", "JROTC", "MOAA", "NFP", "CPA", "AFB", "USO", "AAUW", "BPOE", "IOOF", "AME", "CME", "GOP", "NRA",
        "AA", "NA", "4-H", "EMS", "PAL", "SPCA", "TV", "FM", "AM", "UMC", "ELCA", "HUD", "VA", "WWII", "AMC", "NJROTC", "BSA", "ESA",
    )
    private val lowerWords = setOf("OF", "THE", "AND", "FOR", "IN", "AT", "ON", "A", "AN", "TO", "BY", "DE", "OR", "WITH")
    private val abbreviations = setOf("ST", "MT", "DR", "JR", "SR", "MR", "MRS", "MS", "FT", "PT", "BLVD", "HWY", "CTR")

    /** "455 HARRISON AVENUE GROUP, INC." -> "455 Harrison Avenue Group, Inc." Names with any lower-case letter are left alone. */
    fun orgName(name: String): String {
        if (name.none { it.isLetter() } || name.any { it.isLowerCase() }) return name
        var first = true
        return name.split(" ").joinToString(" ") { w ->
            val out = caseWord(w, first)
            if (w.isNotEmpty()) first = false
            out
        }
    }

    private fun caseWord(w: String, first: Boolean): String {
        val trimChars = ",.;:()\"'&!?".toSet()
        val core = w.trim { it in trimChars }
        if (core.isEmpty()) return w
        val i = w.indexOf(core)
        if (i < 0) return w
        return w.substring(0, i) + caseCore(core, first, w) + w.substring(i + core.length)
    }

    private fun caseCore(c: String, first: Boolean, wholeWord: String): String {
        if (c in keepUpper || wholeWord.trim { it in ",;:()".toSet() } in keepUpper) return c
        if (!first && c in lowerWords) return c.lowercase()
        for (sep in listOf("-", "/")) {
            if (c.contains(sep)) {
                return c.split(sep).mapIndexed { i, part -> caseCore(part, first && i == 0, part) }.joinToString(sep)
            }
        }
        if (c.firstOrNull()?.isDigit() == true) return c.lowercase()
        val letters = c.filter { it.isLetter() }
        if (letters.length >= 2 && c !in abbreviations && letters.none { it in "AEIOUY" }) return c
        if (c.startsWith("MC") && c.length > 3) return "Mc" + c.substring(2, 3) + c.substring(3).lowercase()
        if (c.startsWith("O'") && c.length > 2) return "O'" + c.substring(2, 3) + c.substring(3).lowercase()
        return c.take(1) + c.drop(1).lowercase()
    }
}

fun String.capitalizeFirst(): String = if (isEmpty()) this else substring(0, 1).uppercase() + substring(1)

/** Dates in Bay County time (America/Chicago). */
object Dates {
    val chicago: ZoneId = ZoneId.of("America/Chicago")
    private val dayRe = Regex("^\\d{4}-\\d{2}-\\d{2}$")
    private val shownDay = DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US).withZone(chicago)
    private val shownTime = DateTimeFormatter.ofPattern("MMM d, yyyy 'at' h:mm a", Locale.US).withZone(chicago)
    private val dayKeyF = DateTimeFormatter.ofPattern("yyyy-MM-dd", Locale.US).withZone(chicago)

    /** Parses "2026-10-27T18:00:00-05:00" or "2026-10-27" (midnight in Bay County). */
    fun parse(s: String): Instant? {
        if (s.length == 10 && dayRe.matches(s)) {
            return runCatching { LocalDate.parse(s).atStartOfDay(chicago).toInstant() }.getOrNull()
        }
        if (s.length > 10 && s.contains("T")) {
            return runCatching { OffsetDateTime.parse(s).toInstant() }.getOrNull()
                ?: runCatching { Instant.parse(s) }.getOrNull()
        }
        return null
    }

    fun display(d: Instant, hasTime: Boolean): String = (if (hasTime) shownTime else shownDay).format(d)

    /** Calendar day in Bay County time, for grouping. */
    fun dayKey(d: Instant): String = dayKeyF.format(d)

    fun format(d: Instant, pattern: String): String =
        DateTimeFormatter.ofPattern(pattern, Locale.US).withZone(chicago).format(d)
}
