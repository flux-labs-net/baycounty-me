package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import me.baycounty.app.ui.*
import me.baycounty.kit.AddressMatch
import me.baycounty.kit.AddressParser
import me.baycounty.kit.HomeTiles

/** First launch (and the Home tab's "Set up your home" tile): where you live and whether you own or rent. Owners'
 *  Home tab leads with the tax bill; renters' with utilities and services. Both answers stay on this phone.
 *  Mirrors the iOS HomeSetupView. */
@Composable
fun HomeSetupScreen(onDone: () -> Unit) {
    val store = LocalStore.current
    var query by rememberSaveable { mutableStateOf("") }
    var results by remember { mutableStateOf<List<AddressMatch>>(emptyList()) }
    var message by remember { mutableStateOf<String?>(null) }
    var picked by remember { mutableStateOf(store.home) }
    var tenure by remember { mutableStateOf(store.tenure ?: HomeTiles.Tenure.OWN) }

    LaunchedEffect(query) {
        val q = query.trim()
        if (q.length < 3) { results = emptyList(); message = null; return@LaunchedEffect }
        delay(300)
        if (AddressParser.parse(q)?.tokens.isNullOrEmpty()) {
            results = emptyList(); message = "Start with the house number, then the street (for example \"1614 Ohio\")."
            return@LaunchedEffect
        }
        try {
            val r = store.gis.search(q)
            results = r.matches
            message = if (r.matches.isEmpty()) "No matching Bay County address. Try just the number and street name." else null
        } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Exception) {
            message = "Bay County's map server didn't answer. Try again in a moment."
        }
    }

    fun finish(save: Boolean) {
        if (save) {
            picked?.let { store.saveHome(it) }
            store.saveTenure(tenure)
        }
        store.markSetupSeen()
        onDone()
    }

    Column(Modifier.fillMaxSize().background(Brand.canvas).systemBarsPadding().imePadding()) {
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(22.dp),
        ) {
            BayMark(Modifier.size(28.dp))
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Where do you live?", style = T.title2, color = Brand.text, modifier = Modifier.semantics { heading() })
                Text("We use it to show what applies to you: trash day, your officials, your schools. It stays on your phone.",
                    style = T.subhead, color = Brand.secondary)
            }
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Street address", style = T.subheadBold, color = Brand.text)
                val p = picked
                if (p != null && query.isEmpty()) {
                    Row(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Icon(icon("house.fill"), null, tint = Brand.navy)
                        Column(Modifier.weight(1f)) {
                            Text(p.display, style = T.body.copy(fontWeight = FontWeight.Medium), color = Brand.text)
                            if (p.subtitle.isNotEmpty()) Text(p.subtitle, style = T.caption, color = Brand.secondary)
                        }
                        TextButton(onClick = { picked = null }) { Text("Change", style = T.subheadBold, color = Brand.navy) }
                    }
                } else {
                    FilterField(query, "e.g. 825 Ohio Ave") { query = it }
                    message?.let { Text(it, style = T.footnote, color = Brand.secondary) }
                    if (results.isNotEmpty()) CardList {
                        val shown = results.take(5)
                        shown.forEachIndexed { i, m ->
                            Box(Modifier.clickable(role = Role.Button) { picked = m; query = ""; results = emptyList() }) {
                                RowLabel(m.display, m.subtitle.ifEmpty { null }, "house", chevron = false)
                            }
                            if (i < shown.lastIndex) RowDivider(50.dp)
                        }
                    }
                }
            }
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Do you own or rent this home?", style = T.subheadBold, color = Brand.text)
                TenurePicker(tenure) { tenure = it }
            }
        }
        Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp).padding(top = 8.dp, bottom = 8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Button(
                onClick = { finish(true) },
                modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp).testTag("setupContinue"),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Brand.navyFill, contentColor = Color.White),
            ) { Text("Continue", style = T.headline) }
            TextButton(onClick = { finish(false) }, modifier = Modifier.heightIn(min = 44.dp)) {
                Text("Skip for now", style = T.subhead, color = Brand.navy)
            }
        }
    }
}

/** Own, rent, or rather not say: three cards with a radio on the picked one. Used on setup and in Settings. */
@Composable
fun TenurePicker(selection: HomeTiles.Tenure, onPick: (HomeTiles.Tenure) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        for (t in HomeTiles.Tenure.entries) {
            val on = selection == t
            val shape = RoundedCornerShape(14.dp)
            Row(
                Modifier.fillMaxWidth().card(14.dp)
                    .border(if (on) 1.5.dp else 0.dp, if (on) Brand.navy else Color.Transparent, shape)
                    .selectable(selected = on, role = Role.RadioButton) { onPick(t) }
                    .padding(horizontal = 6.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = on, onClick = null, colors = RadioButtonDefaults.colors(selectedColor = Brand.navy), modifier = Modifier.padding(8.dp))
                Column(Modifier.weight(1f).padding(end = 8.dp)) {
                    Text(t.label, style = T.subheadBold, color = Brand.text)
                    Text(t.detail, style = T.caption, color = Brand.secondary)
                }
            }
        }
    }
}
