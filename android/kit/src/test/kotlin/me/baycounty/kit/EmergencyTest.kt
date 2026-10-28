package me.baycounty.kit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class EmergencyTest {
    @Test fun feedParses() {
        val json = """{"headline":"Hurricane Warning in effect.","checked_at":"2026-10-27T21:00:00.000Z","counts":{"weather":1,"boil-water":2},
            "notices":[{"notice_id":"nws:1","kind":"weather","event":"Hurricane Warning","severity":"extreme","title":"Hurricane Warning"}],
            "shelters":[{"shelter_id":"a","name":"A","status":"open","type":"general"},{"shelter_id":"b","name":"B","status":"closed","type":"general"}],
            "zones":[{"zone":"A","ordered":true}]}"""
        val f = Emergency.parseFeed(json.toByteArray())
        assertEquals("Hurricane Warning in effect.", f.headline)
        assertNotNull(f.checkedAt)
        assertEquals(2, f.count("boil-water"))
        assertEquals(1, f.sheltersOpen)
        assertEquals(true, f.zones.first().bool("ordered"))
    }

    @Test fun headlineMatchesTheSite() {
        val r = Row.decodeList("""[{"kind":"evacuation","zones":"A, B"},{"kind":"weather","event":"Tornado Watch"}]""")
        assertEquals("No weather warnings or evacuation orders right now.", Emergency.headline(emptyList()))
        assertEquals("Evacuation order in effect for Zones A, B.", Emergency.headline(r))
        assertEquals("1 weather advisory or watch in effect.", Emergency.headline(listOf(r[1])))
    }

    @Test fun repeatedNoticeShowsOnceWithUpdatedLine() {
        val r = Row.decodeList("""[{"notice_id":"alert:lh:145","kind":"utility","status":"active","issued":"2026-10-23T14:42:27.000Z","first_posted":"2026-10-23T14:35:50.000Z"},
            {"notice_id":"alert:lh:144","kind":"utility","status":"active","issued":"2026-10-23T14:35:50.000Z","same_as":"alert:lh:145"}]""")
        val f = Emergency.offlineFeed(r, emptyList(), emptyList())
        assertEquals(listOf("alert:lh:145"), f.notices.map { it.string("notice_id") })
        assertEquals("Posted Oct 23, 9:35 AM · Updated Oct 23, 9:42 AM", Emergency.posted(r[0]))
        assertEquals("Oct 23, 9:35 AM", Emergency.posted(r[1]))
    }

    @Test fun zoneAnswer() {
        val json = """{"found":true,"zone":"D","address":{"address":"825 OHIO AVE","community":"LYNN HAVEN"},"point":{"lat":30.24,"lng":-85.64},
            "what_to_do":"You're in evacuation Zone D.","orders_now":[{"title":"Order for Zone A","includes_you":false}],"nearest_shelters":[{"name":"Deane Bozeman","miles":4.2}]}"""
        val z = Emergency.parseZone(json.toByteArray())
        assertEquals("D", z.zone)
        assertEquals("825 OHIO AVE, LYNN HAVEN", z.address)
        assertFalse(z.orders.first().includesYou)
        assertEquals(1, z.nearestShelters.size)
        assertEquals("/api/v1/evacuation-zone?address=825%20Ohio%20Ave", Emergency.zonePath("825 Ohio Ave"))
    }

    @Test fun rebuildMoneyAddsUpLikeTheSite() {
        val rows = Repo.rows("rebuild-money")
        val all = Emergency.rebuild(rows)
        assertEquals("other", all.last().zip)
        assertEquals(rows.sumOf { it.number("amount_paid") ?: 0.0 }, all.sumOf { it.total }, 1.0)
        val michael = Emergency.rebuild(rows, Emergency.Storm.MICHAEL)
        assertTrue(michael.first().total > 1_000_000)
        val byZip = all.associate { it.zip to it.total }
        assertTrue(michael.all { it.total <= (byZip[it.zip] ?: 0.0) + 0.01 })
    }

    @Test fun prepAndShelters() {
        val topics = Emergency.prepTopics(Repo.rows("hurricane-prep"))
        assertEquals("Before the season", topics.first().first)
        val shelters = Repo.rows("emergency-shelters")
        assertEquals(shelters.size, Emergency.sheltersByType(shelters).sumOf { it.second.size })
    }

    @Test fun pushBodyHasNoAddress() {
        val o = BCJson.parseToJsonElement(Emergency.pushBody("ab", "android", setOf("water", "agenda"), listOf("pcb"), 30.1, -85.6, 1.0, "1.0")).objectValue!!
        assertEquals(listOf("agenda", "water"), o["topics"]!!.arrayValue!!.map { it.stringValue })
        assertEquals(30.1, o["lat"]!!.doubleValue!!, 0.0)
        assertNull(o["address"])
    }
}
