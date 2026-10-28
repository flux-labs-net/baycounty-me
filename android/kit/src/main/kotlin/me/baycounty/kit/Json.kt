package me.baycounty.kit

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject

/** The one JSON reader: tolerant of fields the app doesn't know yet, so new site data never breaks it. */
val BCJson = Json {
    ignoreUnknownKeys = true
    explicitNulls = false
    coerceInputValues = true
    isLenient = true
}

/** True for null, blank strings, and empty arrays or objects. */
val JsonElement.isEmptyValue: Boolean
    get() = when (this) {
        is JsonNull -> true
        is JsonPrimitive -> isString && content.isBlank()
        is JsonArray -> isEmpty()
        is JsonObject -> isEmpty()
    }

/** Text for a string, number or bool. Whole numbers print without ".0". */
val JsonElement.stringValue: String?
    get() {
        if (this !is JsonPrimitive || this is JsonNull) return null
        if (isString) return content
        booleanOrNull?.let { return if (it) "true" else "false" }
        val d = doubleOrNull ?: return content
        return if (d == Math.rint(d) && Math.abs(d) < 1e15) d.toLong().toString() else d.toString()
    }

val JsonElement.doubleValue: Double?
    get() {
        if (this !is JsonPrimitive || this is JsonNull) return null
        if (isString) return content.replace(",", "").toDoubleOrNull()
        if (booleanOrNull != null) return null
        return doubleOrNull
    }

val JsonElement.boolValue: Boolean?
    get() {
        if (this !is JsonPrimitive || this is JsonNull) return null
        if (isString) return when (content.lowercase()) { "true", "yes" -> true; "false", "no" -> false; else -> null }
        return booleanOrNull
    }

val JsonElement.arrayValue: List<JsonElement>? get() = this as? JsonArray
val JsonElement.objectValue: Map<String, JsonElement>? get() = this as? JsonObject

/** Every piece of text in the value, for search. */
val JsonElement.searchText: String
    get() = when (this) {
        is JsonNull -> ""
        is JsonPrimitive -> stringValue ?: ""
        is JsonArray -> joinToString(" ") { it.searchText }
        is JsonObject -> values.joinToString(" ") { it.searchText }
    }

/** One record from a dataset. Dataset rows are heterogeneous, so values stay as JSON. */
data class Row(val id: Int, val values: Map<String, JsonElement>) {
    operator fun get(key: String): JsonElement? = values[key]

    fun string(key: String): String? {
        val v = values[key] ?: return null
        if (v.isEmptyValue) return null
        return v.stringValue
    }

    fun number(key: String): Double? = values[key]?.doubleValue
    fun bool(key: String): Boolean? = values[key]?.boolValue

    fun strings(key: String): List<String> =
        values[key]?.arrayValue?.mapNotNull { it.stringValue }?.filter { it.isNotEmpty() } ?: emptyList()

    /** First non-empty string among keys. */
    fun first(keys: List<String>): String? = keys.firstNotNullOfOrNull { string(it) }

    /** First number among keys. */
    fun firstNumber(keys: List<String>): Double? = keys.firstNotNullOfOrNull { number(it) }

    fun url(key: String): String? = string(key)?.takeIf { it.startsWith("http") }

    /** Lower-cased text of every value. */
    val searchText: String by lazy { values.values.joinToString(" ") { it.searchText }.lowercase() }

    companion object {
        fun decodeList(bytes: ByteArray): List<Row> = decodeList(bytes.decodeToString())
        fun decodeList(text: String): List<Row> =
            BCJson.parseToJsonElement(text).jsonArray.mapIndexed { i, e -> Row(i, e.jsonObject) }

        /** Rows from an /api/v1/datasets response ({data: [...]}) or a plain download ([...]). */
        fun decodeRows(bytes: ByteArray): List<Row> {
            val e = BCJson.parseToJsonElement(bytes.decodeToString())
            val list = (e as? JsonObject)?.get("data") as? JsonArray ?: e.jsonArray
            return list.mapIndexed { i, x -> Row(i, x.jsonObject) }
        }
    }
}
