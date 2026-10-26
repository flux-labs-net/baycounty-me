package me.baycounty.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.DatasetSpec
import me.baycounty.kit.Format

/** Every dataset on the site, grouped the way the website's menu groups them. */
@Composable
fun ExploreScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    Screen("Every dataset", onRefresh = { store.loadCatalog() }, spacing = 22) {
        if (store.catalog == null) item {
            val e = store.errors["catalog"]
            if (e != null) Unavailable("Couldn't load the data list", e) else Loading()
        }
        for ((section, datasets) in store.exploreSections) item(key = section.name) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                EyebrowHeader(section.label)
                CardList {
                    datasets.forEachIndexed { i, d ->
                        Row(
                            Modifier.fillMaxWidth().clickable { nav.push(if (d.id == "cra-payments") Route.CRA else Route.Dataset(d.id)) }.padding(horizontal = 14.dp, vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            Icon(icon(DatasetSpec.forId(d.id).symbol), null, tint = Brand.navy, modifier = Modifier.size(22.dp))
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text(d.title, style = T.body.copy(fontWeight = FontWeight.Medium), color = Brand.text)
                                d.description?.let { Text(it, style = T.caption, color = Brand.secondary, maxLines = 2, overflow = TextOverflow.Ellipsis) }
                            }
                            d.rows?.let { Text(Format.number(it.toDouble()), style = T.caption, color = Brand.secondary) }
                            Chevron()
                        }
                        if (i < datasets.lastIndex) RowDivider(48.dp)
                    }
                }
            }
        }
        store.catalog?.let { c ->
            item {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    CardList {
                        WebRow("Download every dataset", "${BayCountyClient.SITE}/open-data", symbol = "arrow.down.circle")
                        RowDivider(50.dp)
                        WebRow("API for developers", "${BayCountyClient.SITE}/developers", symbol = "curlybraces")
                    }
                    c.updated?.let { Text("Data updated $it.", style = T.footnote, color = Brand.secondary) }
                    c.license?.let { Text(it, style = T.footnote, color = Brand.secondary) }
                }
            }
        }
    }
}
