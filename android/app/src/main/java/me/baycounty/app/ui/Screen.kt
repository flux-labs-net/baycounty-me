package me.baycounty.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

/** Where screens start scrolled to, in pixels. Only the screenshot tests change it, to capture long pages in parts. */
val LocalScrollStart = androidx.compose.runtime.staticCompositionLocalOf { 0 }

/** An icon-only toolbar button (toolbar items never carry text). */
@Composable
fun ToolbarIcon(symbol: String, description: String, onClick: () -> Unit) {
    IconButton(onClick = onClick) { Icon(icon(symbol), description, tint = Brand.navy) }
}

/**
 * A screen: a top bar (back arrow when there's somewhere to go back to, the title, icon actions) over a scrolling
 * column on the canvas with the standard 16dp side margins.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun Screen(
    title: String,
    navigationIcon: (@Composable () -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
    onRefresh: (suspend () -> Unit)? = null,
    listState: LazyListState = rememberLazyListState(0, LocalScrollStart.current),
    spacing: Int = 26,
    content: LazyListScope.() -> Unit,
) {
    val nav = LocalNav.current
    val canGoBack = nav.stack().isNotEmpty()
    Column(Modifier.fillMaxSize().background(Brand.canvas)) {
        TopAppBar(
            title = { Text(title, style = T.headline, maxLines = 1, overflow = TextOverflow.Ellipsis) },
            navigationIcon = {
                when {
                    canGoBack -> IconButton(onClick = { nav.pop() }) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Back", tint = Brand.navy) }
                    navigationIcon != null -> navigationIcon()
                }
            },
            actions = actions,
            colors = TopAppBarDefaults.topAppBarColors(containerColor = Brand.canvas, scrolledContainerColor = Brand.canvas, titleContentColor = Brand.text),
        )
        val body: @Composable () -> Unit = {
            LazyColumn(
                Modifier.fillMaxSize(), state = listState, contentPadding = PagePadding,
                verticalArrangement = Arrangement.spacedBy(spacing.dp), content = content,
            )
        }
        if (onRefresh != null) {
            var refreshing by remember { mutableStateOf(false) }
            val scope = rememberCoroutineScope()
            PullToRefreshBox(isRefreshing = refreshing, onRefresh = {
                scope.launch { refreshing = true; try { onRefresh() } finally { refreshing = false } }
            }, modifier = Modifier.fillMaxSize()) { body() }
        } else Box(Modifier.fillMaxSize()) { body() }
    }
}

/** The county mark as the Today toolbar's leading button (opens About). */
@Composable
fun BayMarkButton(onClick: () -> Unit) {
    IconButton(onClick = onClick) { BayMark(Modifier.size(24.dp).padding(1.dp)) }
}
