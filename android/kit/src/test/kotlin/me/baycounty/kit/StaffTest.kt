package me.baycounty.kit

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** The staff app's answers decode and its rules match the Swift StaffTests. */
class StaffTest {
    private val demo = StaffDemo.decode(File(Repo.fixtures, "staff-demo.json").readText())

    @Test fun decodesEveryDemoAnswer() {
        assertTrue(demo.me.admin)
        assertEquals("county", demo.me.workspaces.first().id)
        assertEquals(3, demo.overview.totals.openFlags)
        assertEquals(listOf("county", "lh", "pc"), demo.overview.workspaces.filter { it.needsAttention }.map { it.id })
        assertEquals(1, demo.home.counts.liveAlerts)
        assertEquals(listOf("Live", "Ended"), demo.alerts.alerts.map { it.statusLabel })
        assertEquals("Public hearing or ordinance", demo.notices.posts.first().kindLabel)
        assertFalse(demo.notices.fromRecords.first().editable)
        assertEquals("Budget by year · General Fund, 2026 · amount", demo.flags.flags.first().subject)
    }

    @Test fun theAppsShareOneDemoFile() {
        assertEquals(File(Repo.fixtures, "staff-demo.json").readText(), File(Repo.root, "ios/BayCountyStaff/Resources/staff-demo.json").readText())
        assertEquals(File(Repo.fixtures, "staff-demo.json").readText(), File(Repo.root, "android/staff/src/main/assets/staff-demo.json").readText())
    }

    @Test fun rolesFollowTheServer() {
        assertTrue(Staff.can("owner", "alert_sender"))
        assertTrue(Staff.can("alert_sender", "publisher"))
        assertFalse(Staff.can("publisher", "alert_sender"))
        assertFalse(Staff.can("auditor", "publisher"))
        assertFalse(Staff.can("nobody", "viewer"))
    }

    @Test fun recordsSendersCanOnlySendRecords() {
        assertTrue(Staff.can("records", "submit"))
        assertTrue(Staff.can("publisher", "submit"))
        assertTrue(Staff.can("owner", "submit"))
        assertFalse(Staff.can("viewer", "submit"))
        assertFalse(Staff.can("auditor", "submit"))
        assertFalse(Staff.can("records", "publisher"))
        assertEquals("Records sender", Staff.roleLabel["records"])
    }

    @Test fun decodesSentRecords() {
        val s = demo.submissions!!
        assertEquals("lynnhaven@ingest.baycounty.me", s.address)
        assertEquals(listOf(true, false, false), s.due.map { it.current })
        assertEquals(listOf("Waiting for your OK", "Published", "Doesn’t add up"), s.files.map { it.statusLabel })
        assertEquals("Contracts awarded · 6 rows · through Oct 27, 2026", s.files[0].detail)
        assertTrue(s.files[0].canPublish)
        assertTrue(s.files[1].canWithdraw)
        assertFalse(s.files[2].canWithdraw)
        val bad = BCJson.decodeFromString(StaffRecordPreview.serializer(), """{"id":"c2","kind":"contracts","ok":false,"missing":["vendor","amount"]}""")
        assertEquals("We couldn't find: vendor, amount.", bad.problem)
    }

    @Test fun activityReadsAsASentence() {
        assertEquals("utilities@example.gov sent an alert: Boil water: Ohio Ave, 5th to 9th St", demo.home.activity[0].sentence)
        assertEquals("clerk@example.gov signed in", demo.home.activity[3].sentence)
    }

    @Test fun alertsNeedASecondPerson() {
        val a = BCJson.decodeFromString(StaffAlert.serializer(), """{"id":5,"kind":"general","title":"Sandbags","message":"Open","countywide":true,"status":"pending","created_by":"Em1@x.gov","created_at":"2026-10-30T14:00:00Z"}""")
        assertEquals("Needs a second person", a.statusLabel)
        assertFalse(a.canConfirm("em1@x.gov"))
        assertTrue(a.canConfirm("em2@x.gov"))
    }

    @Test fun reachSentence() {
        assertEquals("Reaches 1,240 phones and 1 inbox now, plus the public alert timeline.", StaffReach("water", 1240, 1).sentence)
        assertEquals("Timeline only.", StaffReach(null, 0, 0, "Timeline only.").sentence)
    }

    @Test fun requestsUseTheBearerToken() {
        val c = StaffClient("bcmg_x")
        val r = c.request("alert", body = kotlinx.serialization.json.buildJsonObject { })
        assertEquals("https://baycounty.me/api/gov?action=alert", r.url)
        assertEquals("Bearer bcmg_x", r.headers["Authorization"])
        assertEquals("https://baycounty.me/api/gov?action=reach&kind=road&workspace=lh", c.request("reach", mapOf("workspace" to "lh", "kind" to "road")).url)
    }

    @Test fun dates() {
        assertEquals("Oct 30, 8:05 AM", Staff.whenOf("2026-10-30T13:05:00Z"))
        assertEquals("Nov 12, 2026", Staff.whenOf("2026-11-12"))
        assertEquals("2 days", Staff.hoursLabel(48))
    }
}
