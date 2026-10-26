package me.baycounty.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import me.baycounty.kit.Glossary

/** A glossary term in plain English, in a sheet over the current screen. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TermSheet(term: Glossary.Term, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(), containerColor = Brand.canvas) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, bottom = 32.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(term.term, style = T.title3, color = Brand.text, modifier = Modifier.weight(1f))
                TextButton(onClick = onDismiss) { Text("Done", style = T.subheadBold, color = Brand.navy) }
            }
            Text(term.simple, style = T.body, color = Brand.text, modifier = Modifier.fillMaxWidth().card().padding(14.dp))
            term.more?.let {
                EyebrowHeader("More detail")
                Text(it, style = T.subhead, color = Brand.text, modifier = Modifier.fillMaxWidth().card().padding(14.dp))
            }
            term.example?.let {
                EyebrowHeader("Example")
                Text(it, style = T.subhead, color = Brand.text, modifier = Modifier.fillMaxWidth().card().padding(14.dp))
            }
        }
    }
}
