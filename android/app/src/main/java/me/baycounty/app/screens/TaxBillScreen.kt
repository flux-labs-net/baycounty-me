package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.Format
import me.baycounty.kit.HomeTiles
import me.baycounty.kit.TaxCalculator

/** The Home tab's tax bill tile, opened: the yearly estimate, who gets it, how it changed from last year, and where to
 *  go deeper. Same estimate as the tax calculator. Mirrors the iOS TaxBillView. */
@Composable
fun TaxBillScreen(districtID: String?) {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.loadTax() }
    val m = store.taxModel
    Screen("Your tax bill", onRefresh = { store.loadTax() }, spacing = 18) {
        if (m == null || m.districts.isEmpty()) {
            item { val e = store.appError("tax.json"); if (e != null) Unavailable("Couldn't load your tax bill", e) else Loading() }
            return@Screen
        }
        val d = m.districts.firstOrNull { it.id == districtID } ?: m.districts.firstOrNull { it.id == store.savedDistrict } ?: m.districts.first()
        val value = HomeTiles.SAMPLE_VALUE
        val e = TaxCalculator.estimate(m, d, value, true)
        val name = { g: String -> if (g == "city") TaxCalculator.cityName(m, d) else m.groupName(g) }
        val change = if (e.trend.size >= 2) e.trend[e.trend.size - 1].total - e.trend[e.trend.size - 2].total else null
        item {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Your tax bill · ${e.trend.lastOrNull()?.fy.orEmpty()}".uppercase(),
                    style = T.caption.copy(fontWeight = FontWeight.SemiBold, letterSpacing = 0.6.sp), color = Brand.secondary,
                    modifier = Modifier.semantics { heading() })
                Text(Format.money(e.total), style = TextStyle(fontFamily = T.bigNumber.fontFamily, fontWeight = FontWeight.SemiBold, fontSize = 40.sp, lineHeight = 46.sp), color = Brand.text)
                Text("Estimate for a ${Format.compactMoney(value)} home with homestead in ${d.label}.", style = T.subhead, color = Brand.secondary)
            }
        }
        item {
            Column(Modifier.fillMaxWidth().card(16.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                StackBar(e.byGroup.map { Triple(name(it.group), it.amount, taxColor(it.group)) })
                for (g in e.byGroup) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Box(Modifier.size(10.dp).background(taxColor(g.group), RoundedCornerShape(3.dp)))
                        Text(name(g.group), style = T.body, color = Brand.text, modifier = Modifier.weight(1f))
                        Text(Format.money(g.amount), style = T.body.copy(fontWeight = FontWeight.SemiBold), color = Brand.text)
                    }
                }
            }
        }
        if (change != null && kotlin.math.abs(change) >= 1) item {
            Row(
                Modifier.fillMaxWidth().background(Brand.good.copy(alpha = 0.12f), RoundedCornerShape(14.dp)).padding(14.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Icon(icon(if (change > 0) "arrow.up.right" else "arrow.down.left"), null, tint = Brand.text, modifier = Modifier.size(18.dp))
                Text("${if (change > 0) "Up" else "Down"} ${Format.money(kotlin.math.abs(change))} from last year for the same home.", style = T.subhead, color = Brand.text)
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                EyebrowHeader("Go deeper")
                CardList {
                    store.home?.let { home ->
                        RouteRow(Route.Address(home), "Exact estimate for your home", home.display, "house")
                        RowDivider(50.dp)
                    }
                    RouteRow(Route.TaxCalculator(d.id, value, true), "Every line, any home value", symbol = "percent")
                    RowDivider(50.dp)
                    RouteRow(Route.Dataset("fees-assessments"), "Fees on your bill", symbol = "doc.plaintext")
                    RowDivider(50.dp)
                    RouteRow(Route.Dataset("property-tax-exemptions"), "Exemptions you may qualify for", symbol = "shield")
                    RowDivider(50.dp)
                    RouteRow(Route.Dataset("property-tax-rates"), "Who set these rates", "Every taxing authority, by year", "chart.line.uptrend.xyaxis")
                }
            }
        }
    }
}
