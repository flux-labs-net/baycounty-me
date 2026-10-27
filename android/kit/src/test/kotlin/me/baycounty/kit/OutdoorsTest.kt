package me.baycounty.kit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class OutdoorsTest {
    @Test fun beachesRead() {
        val cond = Repo.rows("beach-conditions")
        assertTrue(Outdoors.forecast(cond).isNotEmpty())
        assertEquals("Double red", Outdoors.legend(cond).first().string("flag_color"))
        val sites = Outdoors.waterSites(Repo.rows("beach-water-sites"))
        assertTrue(sites.size >= 10)
        assertEquals(sites.map { it.number("longitude") }, sites.map { it.number("longitude") }.sortedBy { it })
        val access = Repo.rows("beach-access")
        assertTrue(access.size > 100)
        val wc = Outdoors.accesses(access, Outdoors.AccessFilter.WHEELCHAIR)
        assertTrue(wc.isNotEmpty() && wc.all { it.bool("wheelchair_access") == true })
        assertNotNull(Outdoors.directions(access[0]))
    }

    @Test fun parksRead() {
        val parks = Repo.rows("parks")
        assertTrue(parks.size > 50)
        val pg = Outdoors.parks(parks, Outdoors.ParkFilter.PLAYGROUND)
        assertTrue(pg.isNotEmpty() && pg.all { Outdoors.parkTags(it).contains("Playground") })
        assertTrue(Outdoors.parks(parks, gov = "pcb").all { it.string("gov_id") == "pcb" })
        assertTrue(Repo.rows("boat-ramps").isNotEmpty())
        assertTrue(Repo.rows("recreation-departments").size >= 8)
    }

    @Test fun poorNowWindow() {
        val rows = Row.decodeList("""[{"active":true,"latest_rating":"Poor","latest_date":"2026-10-01","longitude":-85.9},
            {"active":true,"latest_rating":"Poor","latest_date":"2026-05-01","longitude":-85.8},
            {"active":true,"latest_rating":"Good","latest_date":"2026-10-20","longitude":-85.7}]""")
        assertEquals(1, Outdoors.poorNow(rows, "2026-10-27").size)
    }
}
