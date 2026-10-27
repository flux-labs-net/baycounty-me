package me.baycounty.kit

import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * The Android kit must give the same answers as the site's JavaScript and API, using the same fixtures as the
 * iOS ApiParityTests and WebParityTests (made by ios/scripts/make_fixtures.js).
 */
class ParityTest {
    @Serializable data class ApiFixture(val officials: List<Officials>, val budget: List<Budget>) {
        @Serializable data class Officials(val gov: String, val year: Int, val seats: List<Seat>) {
            @Serializable data class Seat(val seat: String, val holders: List<String>)
        }
        @Serializable data class Budget(
            val gov: String, val basis: String, val from: Int, val to: Int, val totals: List<L>,
            val sections: Map<String, List<L>>, val notes: List<String>, val up: String? = null, val down: String? = null,
        ) {
            @Serializable data class L(val key: String, val from: Double? = null, val to: Double? = null)
        }
    }

    @Serializable data class WebFixture(val tax: List<Tax>, val a3: List<A3>, val parse: List<Parse>, val shards: List<Shard>) {
        @Serializable data class Tax(val d: String, val v: Double, val h: Boolean, val total: Double, val trend: List<Double>)
        @Serializable data class A3(val d: String, val v: Double, val k: String, val totals: List<Double>)
        @Serializable data class Parse(val input: String, val parsed: P? = null, val where: List<String>? = null) {
            @Serializable data class P(val house: String, val unit: String, val place: String, val toks: List<Tok>) {
                @Serializable data class Tok(val alts: List<String>, val kind: String, val word: Boolean? = null, val partial: Boolean? = null)
            }
        }
        @Serializable data class Shard(val p: String, val ex: String, val nav: String)
    }

    private val api = BCJson.decodeFromString(ApiFixture.serializer(), File(Repo.fixtures, "api-parity.json").readText())
    private val web = BCJson.decodeFromString(WebFixture.serializer(), File(Repo.fixtures, "web-parity.json").readText())

    @Test fun whoHeldEachSeatMatchesTheAPI() {
        val terms = Repo.rows("officeholder-terms")
        for (c in api.officials) {
            val seats = Officeholders.inOffice(terms, c.gov, year = c.year)
            assertEquals("${c.gov} FY${c.year}", c.seats.map { it.seat }, seats.map { it.seat })
            for ((s, e) in seats.zip(c.seats)) {
                val got = s.holders.map { (it.personName.ifEmpty { "null" }) + (if (it.partOfPeriod) "*" else "") }
                assertEquals("${c.gov} FY${c.year} ${s.seat}", e.holders, got)
            }
        }
    }

    @Test fun budgetComparisonMatchesTheAPI() {
        val budgets = Repo.rows("budget-years")
        for (c in api.budget) {
            val label = "${c.gov} ${c.basis}"
            val r = BudgetCompare.compare(budgets, c.gov, BudgetCompare.Basis.entries.first { it.key == c.basis })
            assertNotNull(label, r); r!!
            assertEquals(label, c.from, r.from)
            assertEquals(label, c.to, r.to)
            fun same(got: List<BudgetCompare.Line>, want: List<ApiFixture.Budget.L>, what: String) {
                assertEquals("$label $what", want.map { it.key }, got.take(5).map { it.key })
                for ((g, w) in got.zip(want)) {
                    assertEquals("$label $what ${g.key}", w.from ?: -1.0, g.from ?: -1.0, 0.5)
                    assertEquals("$label $what ${g.key}", w.to ?: -1.0, g.to ?: -1.0, 0.5)
                }
            }
            same(r.totals, c.totals, "totals")
            for ((k, want) in c.sections) same(r.sections.first { it.key == k }.lines, want, k)
            assertEquals(label, c.notes, r.notes)
            assertEquals(label, c.up, r.biggestIncrease?.key)
            assertEquals(label, c.down, r.biggestDecrease?.key)
        }
    }

    @Test fun fiscalYearWindows() {
        assertEquals("2025-10-01" to "2026-09-30", Officeholders.fyWindow("lh", 2026))
        assertEquals("2023-07-01" to "2024-06-30", Officeholders.fyWindow("schools", 2024))
    }

    @Test fun craIncrementHeadlineMatchesThePage() {
        val agencies = Repo.rows("cra-agencies"); val years = Repo.rows("cra-tax-increment")
        val h = CRAIncrement.headline(agencies, years)!!
        assertEquals(7, h.agencies)
        assertTrue(h.firstYear >= Cutoff.FIRST_YEAR)
        assertTrue(h.total > h.county)
        assertTrue(h.toComeHigh > h.toComeLow)
        val series = CRAIncrement.byYear(years)
        assertEquals(h.firstYear, series.first().fiscalYear)
        assertEquals(h.total, series.first { it.fiscalYear == h.lastYear }.amount, 1.0)
        assertTrue(series.any { it.projected })
    }

    @Test fun personLinksIncludeTermsAndPastRaces() {
        val all = RecordLinks.personDatasets.associateWith { Repo.rows(it) }
        val recs = RecordLinks.recordsForPerson("robert-carroll", all).toMap()
        assertFalse(recs["officeholder-terms"].isNullOrEmpty())
        assertFalse(recs["campaign-history"].isNullOrEmpty())
        assertFalse(Officeholders.terms(all["officeholder-terms"]!!, "robert-carroll").isEmpty())
        assertEquals(Cutoff.FIRST_YEAR, Officeholders.years(all["officeholder-terms"]!!, "lh").last())
    }

    @Test fun taxCalculatorMatchesWebsite() {
        val tax = BCJson.decodeFromString(TaxModel.serializer(), Repo.app("tax.json"))
        for (c in web.tax) {
            val d = tax.districts.first { it.id == c.d }
            val e = TaxCalculator.estimate(tax, d, c.v, c.h)
            assertEquals("${c.d} ${c.v} ${c.h}", c.total, e.total, 0.005)
            assertEquals(c.trend.size, e.trend.size)
            for ((a, b) in e.trend.map { it.total }.zip(c.trend)) assertEquals("${c.d} trend", b, a, 0.005)
        }
    }

    @Test fun amendment3MatchesWebsite() {
        val a3 = BCJson.decodeFromString(Amendment3Model.serializer(), Repo.app("amendment3.json"))
        for (c in web.a3) {
            val d = a3.districts.first { it.id == c.d }
            val s = Amendment3Calculator.scenarios(a3, d, c.v, Amendment3Calculator.Kind.entries.first { it.key == c.k })
            assertEquals(3, s.size)
            for ((a, b) in s.map { it.total }.zip(c.totals)) assertEquals("${c.d} ${c.v} ${c.k}", b, a, 0.005)
        }
    }

    @Test fun addressParserMatchesWebsite() {
        for (c in web.parse) {
            val p = AddressParser.parse(c.input)
            val want = c.parsed
            if (want == null) { assertNull(c.input, p); continue }
            assertNotNull("no parse: ${c.input}", p); p!!
            assertEquals(c.input, want.house, p.house)
            assertEquals(c.input, want.unit, p.unit)
            assertEquals(c.input, want.place, p.place)
            assertEquals(c.input, want.toks.map { it.alts }, p.tokens.map { it.alts })
            assertEquals(c.input, want.toks.map { it.kind }, p.tokens.map { it.kind.name.lowercase() })
            val all = listOf(AddressParser.Token.Kind.NAME, AddressParser.Token.Kind.TYPE, AddressParser.Token.Kind.DIR)
            assertEquals(c.input, c.where?.get(0), AddressParser.whereClause(p, all))
            assertEquals(c.input, c.where?.get(1), AddressParser.whereClause(p, listOf(AddressParser.Token.Kind.NAME)))
        }
    }

    @Test fun parcelShardsMatchWebsite() {
        for (c in web.shards) {
            assertEquals(c.ex, parcelShard(c.p, 96))
            assertEquals(c.nav, parcelShard(c.p, 128))
        }
    }

    @Test fun glossaryFindsTermsInText() {
        val g = BCJson.decodeFromString(Glossary.serializer(), Repo.app("glossary.json"))
        val found = g.termsIn("Each CRA keeps the tax increment from its district; millage is set each September.").map { it.id }
        assertTrue("$found", "cra" in found)
        assertTrue("$found", "tif" in found)
    }

    @Test fun everyAppDataFileDecodes() {
        val idx = BCJson.decodeFromString(AppDataIndex.serializer(), Repo.app("index.json"))
        assertTrue("tax.json" in idx.files)
        BCJson.decodeFromString(AddressModel.serializer(), Repo.app("address.json"))
        assertTrue(BCJson.decodeFromString(ListSerializer(PageInfo.serializer()), Repo.app("pages.json")).size > 30)
        assertTrue(BCJson.decodeFromString(ListSerializer(SiteUpdate.serializer()), Repo.app("updates.json")).size > 10)
        assertTrue(BCJson.decodeFromString(VendorDirectory.serializer(), Repo.app("vendors.json")).vendors.size > 500)
        val p = BCJson.decodeFromString(PeopleDirectory.serializer(), Repo.app("people.json"))
        assertTrue(p.people.size > 100)
        p.people.firstOrNull { it.id == "clair-pease" }?.let {
            assertEquals(listOf("County Commissioner, District 5 (Chairman)"), it.mainRoles.map { r -> r.role })
            assertEquals("County Commissioner, District 5 (Chairman), Bay County", it.headline)
        }
        p.people.firstOrNull { it.id == "nick-atkinson" }?.let { assertEquals(1, it.mainRoles.size) }
        for (person in p.people) assertFalse(person.id, person.mainRoles.isEmpty())
        // The People list's order: government, then title, then last name, like the site.
        val groups = PeopleDirectory.grouped(p.people)
        assertEquals("Bay County", groups.first().first)
        assertEquals("clair-pease", groups.first().second.first().id)  // the chair leads the county
        for ((_, list) in groups) assertEquals(list.map { it.rank }, list.map { it.rank }.sortedBy { it ?: 99 })
        assertEquals(p.people.size, PeopleEra.CURRENT.let { e -> p.people.count { e.includes(it) } } + p.people.count { PeopleEra.PAST.includes(it) })
        assertTrue(p.people.any { it.isPast } && p.people.any { !it.isPast })
        assertTrue(BCJson.decodeFromString(DonorContracts.serializer(), Repo.app("donor-contracts.json")).matches.size > 50)
        val mm = BCJson.decodeFromString(MoneyMap.serializer(), Repo.app("money-map.json"))
        assertTrue(mm.donors.size > 100)
        val heat = mm.heat()
        assertEquals(15, heat.donors.size)
        assertFalse(heat.govs.isEmpty())
    }
}
