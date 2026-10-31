package me.baycounty.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import me.baycounty.kit.AddressMatch

/** Places a row can lead to. Every tab resolves these the same way (the iOS app's Route). */
sealed class Route {
    data class Dataset(val id: String, val filters: Map<String, String> = emptyMap()) : Route()
    data class Record(val datasetID: String, val rowID: Int) : Route()
    data class Gov(val govID: String) : Route()
    /** One part of a government's screen (GovPart id) on its own screen, for the year the government screen had picked. */
    data class GovPart(val govID: String, val part: String, val year: Int?) : Route()
    data class MeetingDetail(val id: String) : Route()
    object CRA : Route()
    object MyAddress : Route()
    data class Address(val match: AddressMatch) : Route()
    data class TaxCalculator(val districtID: String? = null, val value: Double? = null, val homestead: Boolean? = null) : Route()
    data class Amendment3(val districtID: String? = null, val value: Double? = null, val homestead: Boolean? = null) : Route()
    object Glossary : Route()
    object Vendors : Route()
    data class Vendor(val id: String) : Route()
    object People : Route()
    data class Person(val id: String) : Route()
    object DonorContracts : Route()
    object MoneyMap : Route()
    object Updates : Route()
    object About : Route()
    object Explore : Route()
    object Accountability : Route()
    data class AccountabilityProject(val id: String) : Route()
    object Search : Route()
    data class BudgetCompare(val govID: String? = null) : Route()
    object CRAIncrement : Route()
    object Chambers : Route()
    object Events : Route()
    object Beaches : Route()
    object Parks : Route()
    object Schools : Route()
    object Emergency : Route()
    object HurricanePrep : Route()
    data class Utilities(val match: AddressMatch? = null) : Route()
    object Volunteer : Route()
    object Military : Route()
    object Restaurants : Route()
    data class Restaurant(val license: String) : Route()
    object MyHome : Route()
    object AccountSettings : Route()
    data class GovBudget(val id: String) : Route()
    object Meetings : Route()
    object PublicSafety : Route()
    object Overlaps : Route()
    data class TaxBill(val districtID: String? = null) : Route()
}

/** Home, Around me (the site's Living here), Money, Government and Ask (search and the question box). */
enum class Tab { HOME, LIVING, MONEY, DECIDES, SEARCH }

/** One back stack per tab, like a NavigationStack in each iOS tab. */
class Nav {
    var tab by mutableStateOf(Tab.HOME)
    private val stacks: Map<Tab, SnapshotStateList<Route>> = Tab.entries.associateWith { mutableStateListOf() }

    fun stack(t: Tab = tab): SnapshotStateList<Route> = stacks.getValue(t)
    fun push(r: Route) { stack().add(r) }
    fun pop(): Boolean { val s = stack(); if (s.isEmpty()) return false; s.removeAt(s.lastIndex); return true }
    fun replace(r: Route) { val s = stack(); s.clear(); s.add(r) }
    /** Tapping the current tab again goes back to its first screen. */
    fun select(t: Tab) { if (t == tab) stack().clear() else tab = t }
}
