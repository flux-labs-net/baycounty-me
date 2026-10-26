package me.baycounty.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Format
import me.baycounty.kit.SearchResult

private val suggestions = listOf("Millville", "Front Beach Road", "stormwater", "homestead", "Lynn Haven CRA", "FEMA debris")

/** Search across the whole site, plus shortcuts to browse and to take part. */
@Composable
fun SearchScreen() {
    val store = LocalStore.current
    val o = rememberOpener()
    var query by rememberSaveable { mutableStateOf("") }
    var results by remember { mutableStateOf<List<SearchResult>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    val focus = remember { FocusRequester() }
    val keyboard = LocalSoftwareKeyboardController.current
    LaunchedEffect(Unit) { if (query.isEmpty()) runCatching { focus.requestFocus() } }
    LaunchedEffect(query) {
        val q = query.trim()
        if (q.length < 2) { results = null; error = null; return@LaunchedEffect }
        delay(350)
        busy = true
        try { results = store.client.search(q); error = null }
        catch (e: Exception) { error = "Search needs a connection. Try again when you're online." }
        finally { busy = false }
    }
    Screen("Search", spacing = 20) {
        item {
            OutlinedTextField(
                query, { query = it }, Modifier.fillMaxWidth().focusRequester(focus),
                placeholder = { Text("People, contracts, votes, places", style = T.body) },
                leadingIcon = { Icon(icon("magnifyingglass"), null, tint = Brand.secondary) },
                trailingIcon = { if (query.isNotEmpty()) IconButton(onClick = { query = "" }) { Icon(icon("xmark.circle.fill"), "Clear", tint = Brand.tertiary) } },
                singleLine = true, shape = RoundedCornerShape(14.dp), textStyle = T.body,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { keyboard?.hide() }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = Brand.surface, unfocusedContainerColor = Brand.surface,
                    focusedBorderColor = Brand.navy, unfocusedBorderColor = Brand.hairline, cursorColor = Brand.navy,
                    focusedTextColor = Brand.text, unfocusedTextColor = Brand.text,
                ),
            )
        }
        val r = results
        if (query.trim().length >= 2) {
            when {
                error != null -> item { Unavailable("Couldn't search", error) }
                r == null || (busy && r.isEmpty()) -> item { Loading() }
                r.isEmpty() -> item { Unavailable("No results", "Try a name, a street, or a word from an agenda.", symbol = "magnifyingglass") }
                else -> item {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("${Format.number(r.size)} results", style = T.footnote, color = Brand.secondary)
                        CardList {
                            r.forEachIndexed { i, res ->
                                ResultRow(res) { o.open(res.url?.let { BayCountyClient.absolute(it) }) }
                                if (i < r.lastIndex) RowDivider()
                            }
                        }
                    }
                }
            }
        } else {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    EyebrowHeader("Try")
                    Flow(spacing = 8.dp) {
                        for (s in suggestions) Text(
                            s, style = T.subhead.copy(fontWeight = FontWeight.Medium), color = Brand.navy,
                            modifier = Modifier.clickable { query = s }.card(20.dp).padding(horizontal = 14.dp, vertical = 9.dp),
                        )
                    }
                }
            }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    EyebrowHeader("Browse")
                    val browse = listOf(
                        Triple(Route.Glossary, "Glossary", "character.book.closed"),
                        Triple(Route.Explore, "Every dataset", "square.grid.2x2"),
                        Triple(Route.Vendors, "Companies", "building"),
                        Triple(Route.Accountability, "Accountability console", "checklist"),
                        Triple(Route.People, "People", "person.2"),
                        Triple(Route.Updates, "What's new", "sparkles"),
                        Triple(Route.About, "About and privacy", "info.circle"),
                    )
                    CardList {
                        browse.forEachIndexed { i, (route, t, s) ->
                            RouteRow(route, t, symbol = s)
                            if (i < browse.lastIndex) RowDivider(50.dp)
                        }
                    }
                }
            }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    EyebrowHeader("Take part")
                    val site = BayCountyClient.SITE
                    val web = listOf(
                        Triple("Ask a question", "$site/ask", "bubble.left.and.text.bubble.right"),
                        Triple("Write to officials", "$site/correspondence", "envelope"),
                        Triple("Request public records", "$site/records-request", "doc.text.magnifyingglass"),
                        Triple("Email alerts", "$site/alerts", "bell"),
                    )
                    CardList {
                        web.forEachIndexed { i, (t, u, s) ->
                            WebRow(t, u, symbol = s)
                            if (i < web.lastIndex) RowDivider(50.dp)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ResultRow(r: SearchResult, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 14.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            r.type?.let { Badge(Format.label(it)) }
            Text(r.title ?: "Untitled", style = T.subheadBold, color = Brand.text, maxLines = 2, overflow = TextOverflow.Ellipsis)
            r.summary?.takeIf { it.isNotBlank() }?.let { Text(it, style = T.caption, color = Brand.secondary, maxLines = 2, overflow = TextOverflow.Ellipsis) }
        }
        Chevron()
    }
}
