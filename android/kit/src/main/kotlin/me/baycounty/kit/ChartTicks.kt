package me.baycounty.kit

/** Rules shared by the app's charts: few enough axis labels to read, and nothing before the site's first year. */
object ChartTicks {
    /** Most labels that fit under a phone-width chart. */
    const val PHONE_LABELS = 6

    /** Which of `count` evenly spaced bars get a label, so at most `maxLabels` show. The last bar is always labelled. */
    fun labelIndices(count: Int, maxLabels: Int = PHONE_LABELS): List<Int> {
        if (count <= 0) return emptyList()
        val step = maxOf(1, Math.ceil(count.toDouble() / maxOf(maxLabels, 1)).toInt())
        return (0 until count).filter { (count - 1 - it) % step == 0 }
    }

    fun shownLabels(labels: List<String>, maxLabels: Int = PHONE_LABELS): List<String> = labelIndices(labels.size, maxLabels).map { labels[it] }

    /** Round years to label on a year axis (every 1, 2, 5 or 10 years), at most `maxLabels`. */
    fun yearTicks(years: List<Int>, maxLabels: Int = PHONE_LABELS): List<Int> {
        val lo = years.minOrNull() ?: return emptyList()
        val hi = years.max()
        for (step in listOf(1, 2, 5, 10, 20)) {
            val ticks = (lo..hi).filter { it % step == 0 }
            if (ticks.size <= maxLabels && ticks.isNotEmpty()) return ticks
        }
        return listOf(lo, hi)
    }

    /** Drops anything dated before the site's first year (2016). */
    fun <T> sinceCutoff(items: List<T>, year: (T) -> Int?): List<T> = items.filter { (year(it) ?: Cutoff.FIRST_YEAR) >= Cutoff.FIRST_YEAR }

    /** The year in a label like "FY2024", "2024" or "'24". */
    fun yearOf(label: String): Int? {
        val digits = label.filter { it.isDigit() }
        if (digits.length == 4) return digits.toInt()
        if (digits.length == 2 && label.startsWith("'")) return 2000 + digits.toInt()
        return null
    }
}
