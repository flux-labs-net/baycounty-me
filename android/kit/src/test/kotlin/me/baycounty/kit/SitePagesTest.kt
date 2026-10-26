package me.baycounty.kit

import kotlinx.serialization.builtins.ListSerializer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Keeps the Android app in step with the website. When the site adds a page or a dataset, these fail until the
 * app decides how to show it: add the page to SitePages.pages and give the dataset a DatasetSpec entry.
 */
class SitePagesTest {
    @Test fun everySitePageHasAnAppDecision() {
        val pages = BCJson.decodeFromString(ListSerializer(PageInfo.serializer()), Repo.app("pages.json"))
        val missing = pages.map { it.path }.filter { SitePages.coverage(it) == null }
        assertEquals("Site pages with no app decision. Add each to SitePages.pages: $missing", emptyList<String>(), missing)
    }

    @Test fun everyDatasetPageListIsReal() {
        val ids = Repo.catalog().datasets.map { it.id }.toSet()
        for ((path, c) in SitePages.pages) if (c is SitePages.Coverage.Dataset) {
            assertTrue("$path points at dataset ${c.note}, which the site no longer publishes", c.note in ids)
        }
    }

    @Test fun everyDatasetHasASpec() {
        val missing = Repo.catalog().datasets.map { it.id }.filter { DatasetSpec.known[it] == null && it !in DatasetSpec.ownScreens }
        assertEquals("Datasets with only the generic fallback: $missing", emptyList<String>(), missing)
    }

    /** Android and iOS cover the same pages the same way. */
    @Test fun sameCoverageAsIOS() {
        val swift = File(Repo.root, "ios/BayCountyKit/Sources/BayCountyKit/SitePages.swift").readText()
        val ios = Regex("\"(/[^\"]*)\": \\.(native|dataset|web)\\(").findAll(swift).associate { it.groupValues[1] to it.groupValues[2] }
        val android = (SitePages.pages + SitePages.prefixes).mapValues { it.value::class.simpleName!!.lowercase() }
        assertEquals(ios, android)
    }

    @Test fun accountabilityFileDecodes() {
        val c = BCJson.decodeFromString(AccountabilityConsole.serializer(), File(Repo.data, "accountability.json").readText())
        assertTrue(c.projects.size > 50)
        assertTrue(c.rules.size > 3)
        for (p in c.projects) for (f in p.flags) assertNotNull("${p.id} flag ${f.r} has no rule", c.rule(f.r))
        assertEquals(emptySet<String>(), c.projects.mapNotNull { it.status }.toSet() - AccountabilityConsole.stages.keys)
        assertEquals(emptySet<String>(), c.projects.flatMap { p -> p.ev.map { it.k } }.toSet() - AccountabilityConsole.kinds.keys)
        assertEquals(c.projects.size, c.stats?.projects)
    }

    @Test fun recordProfiles() {
        assertEquals("455 Harrison Avenue Group, Inc.", Format.orgName("455 HARRISON AVENUE GROUP, INC."))
        assertEquals("VFW Post 10085 of Panama City", Format.orgName("VFW POST 10085 OF PANAMA CITY"))
        assertEquals("The ARC of Bay County, Inc.", Format.orgName("THE ARC OF BAY COUNTY, INC."))
        assertEquals("Krewe of St. Andrews Inc", Format.orgName("KREWE OF ST. ANDREWS INC"))
        assertEquals("21st Century Kids-Panama City", Format.orgName("21ST CENTURY KIDS-PANAMA CITY"))
        assertEquals("COO, Vice President and Trustee", RecordProfile.sentenceList(listOf("COO", "Vice President", "Trustee")))
        val ds = "nonprofit-board-members"
        val all = Repo.rows(ds)
        all.firstOrNull { it.string("person_id") == "b_353fe5f7887b" && it.string("nonprofit_id") == "np-sb-n01000008288" }?.let { row ->
            assertEquals("Kathy Bass", RecordProfile.title(ds, row))
            assertEquals("Treasurer and Director", RecordProfile.roleLine(ds, row))
            assertEquals("KB", RecordProfile.initials(ds, row))
            val refs = RecordProfile.refs(ds, row)
            assertEquals(listOf("member:b_353fe5f7887b", "nonprofit:np-sb-n01000008288"), refs.map { it.id })
            assertEquals("https://baycounty.me/profile/member/b_353fe5f7887b", refs[0].profileURL)
            assertEquals(listOf("Current", "Board", "State filing"), RecordProfile.chips(ds, row).map { it.text }.take(3))
        }
        for (d in Repo.catalog().datasets) for (row in Repo.rows(d.id).take(20)) {
            assertFalse(d.id, RecordProfile.title(d.id, row).isEmpty())
            assertTrue(d.id, RecordProfile.facts(d.id, row).size <= 4)
        }
    }
}
