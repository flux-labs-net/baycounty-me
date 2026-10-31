package me.baycounty.kit

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/** The site's dataset catalog (`/downloads/index.json`). */
@Serializable
data class Catalog(
    val updated: String? = null,
    val license: String? = null,
    val datasets: List<DatasetInfo> = emptyList(),
) {
    fun dataset(id: String): DatasetInfo? = datasets.firstOrNull { it.id == id }

    /** The datasets that hold rows for one government (its gov_id column lists it), for a government's "Every record" list.
     *  A dataset with nothing for that government is left off, so the list doesn't open onto empty tables. */
    fun records(govID: String): List<DatasetInfo> =
        datasets.filter { it.id !in DatasetSpec.ownScreens && (it.rows ?: 0) > 0 && it.column("gov_id")?.choices?.contains(govID) == true }
}

@Serializable
data class DatasetInfo(
    val id: String,
    val title: String,
    val description: String? = null,
    val rows: Int? = null,
    val json: String,
    val csv: String? = null,
    val columns: List<Column> = emptyList(),
) {
    @Serializable
    data class Column(val name: String, val type: String? = null, val values: List<JsonElement>? = null) {
        /** Allowed values when the catalog lists a short set (used for filters). */
        val choices: List<String> get() = (values ?: emptyList()).mapNotNull { it.stringValue }.filter { it.isNotEmpty() }
    }

    fun column(name: String): Column? = columns.firstOrNull { it.name == name }

    val csvURL: String? get() = csv?.let { BayCountyClient.absolute(it) }
    val pageURL: String get() = DatasetSpec.forId(id).pageURL ?: "${BayCountyClient.SITE}/open-data"
}
