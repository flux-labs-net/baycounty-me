package me.baycounty.kit

import java.io.File

/** Files the site publishes in this repo, so the Android kit is checked against exactly what baycounty.me serves. */
object Repo {
    val root = File(System.getProperty("repoRoot") ?: "../..").canonicalFile
    val downloads = File(root, "site/public/downloads")
    val appData = File(root, "site/public/data/app")
    val data = File(root, "site/public/data")
    /** Fixtures made by ios/scripts/make_fixtures.js from the site's own JavaScript, shared with the iOS tests. */
    val fixtures = File(root, "ios/BayCountyKit/Tests/BayCountyKitTests/Fixtures")

    fun rows(id: String): List<Row> = Row.decodeList(File(downloads, "$id.json").readBytes())
    fun catalog(): Catalog = BCJson.decodeFromString(Catalog.serializer(), File(downloads, "index.json").readText())
    fun app(name: String): String = File(appData, name).readText()
}
