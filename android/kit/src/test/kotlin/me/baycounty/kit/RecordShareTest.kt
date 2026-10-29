package me.baycounty.kit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Copy and Share text for a record: the same shape on the site (site/share.js), iOS and Android. */
class RecordShareTest {
    @Test fun contractTextHasItsFieldsSourceAndLink() {
        val catalog = Repo.catalog()
        val info = catalog.datasets.first { it.id == "contracts" }
        val row = Repo.rows("contracts").first { DatasetSpec.sourceURL(it) != null }
        val text = RecordShare.text("contracts", row, info.columns, info.title)
        val lines = text.lines()
        assertEquals(DatasetSpec.forId("contracts").title(row), lines.first())
        assertTrue(lines.drop(1).any { ": " in it })
        assertTrue(lines.size <= RecordShare.MAX_FIELDS + 4)
        assertEquals("From “${info.title}” on BayCounty.me", lines[lines.size - 2])
        assertEquals("https://baycounty.me/public-money/contracts", lines.last())
        assertTrue(lines.any { it.startsWith("Source: http") })
    }

    @Test fun ownPageWinsOverTheListPage() {
        val r = Repo.rows("restaurants").first { it.string("page_url") != null }
        assertEquals("https://baycounty.me" + r.string("page_url"), RecordShare.url("restaurants", r))
    }

    @Test fun pageText() {
        assertEquals("Mosey's Downtown\nRestaurant · Panama City\nhttps://baycounty.me/restaurants/moseys-downtown-1304089",
            RecordShare.page("Mosey's Downtown", listOf("Restaurant · Panama City", null, ""), "/restaurants/moseys-downtown-1304089"))
    }
}
