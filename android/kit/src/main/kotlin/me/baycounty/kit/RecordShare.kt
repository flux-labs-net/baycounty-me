package me.baycounty.kit

/**
 * What Copy and Share put out for one record: a clean text summary (its name, then each field as "Label: value") and
 * a link to it on BayCounty.me. Same shape as the website's Share / Copy (site/share.js) and the iOS kit's RecordShare.
 */
object RecordShare {
    /** How many fields the text lists after the name, so a long record stays readable in a message. */
    const val MAX_FIELDS = 10

    /** The record's own page when it has one (page_url), else the site page that lists this dataset, else its source. */
    fun url(datasetID: String, row: Row): String? {
        row.string("page_url")?.takeIf { it.startsWith("/") }?.let { return BayCountyClient.SITE + it }
        DatasetSpec.forId(datasetID).pageURL?.let { return it }
        return DatasetSpec.sourceURL(row)
    }

    /** The text: name, fields, source, where it's from, link. */
    fun text(datasetID: String, row: Row, columns: List<DatasetInfo.Column> = emptyList(), listTitle: String? = null): String {
        val spec = DatasetSpec.forId(datasetID)
        val title = spec.title(row)
        val lines = mutableListOf(title)
        val seen = mutableSetOf(title.lowercase())
        for ((label, value) in DatasetSpec.fields(row, columns)) {
            if (lines.size > MAX_FIELDS) break
            val v = value.replace("\n", " ").trim()
            if (v.isEmpty() || !seen.add(v.lowercase())) continue
            lines += "$label: " + if (v.length > 160) v.take(157) + "…" else v
        }
        val link = url(datasetID, row)
        DatasetSpec.sourceURL(row)?.takeIf { it != link }?.let { lines += "Source: $it" }
        lines += listTitle?.let { "From “$it” on BayCounty.me" } ?: "From BayCounty.me"
        link?.let { lines += it }
        return lines.joinToString("\n")
    }

    /** A page with its own address (a restaurant, a person, a company): its name, a short summary and the link. */
    fun page(title: String, summary: List<String?>, path: String): String =
        (listOf(title) + summary.filterNotNull().filter { it.isNotBlank() } + (BayCountyClient.SITE + path)).joinToString("\n")
}
