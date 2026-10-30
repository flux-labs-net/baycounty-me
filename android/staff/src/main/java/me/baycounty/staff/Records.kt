package me.baycounty.staff

import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.LocalActivityResultRegistryOwner
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Upload
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import me.baycounty.kit.Staff
import me.baycounty.kit.StaffRecordFile
import me.baycounty.kit.StaffRecordPreview
import me.baycounty.kit.StaffSubmissions
import java.text.NumberFormat
import java.util.Locale

/* Send records: a government's staff send the files their accounting system already makes (a check register, a
   budget-vs-actual report, a list of contracts). We read the file, they check what we found, and it goes public with
   the usual privacy rules. Same flow as the Send records tab on the web workspace (/staff) and the iOS app. */

/** On a government's home: what's due, with a way in. */
@Composable
fun RecordsDueCard(s: StaffSubmissions, onOpen: () -> Unit) {
    val late = s.due.filter { !it.current }
    val waiting = s.files.count { it.canPublish }
    val ok = late.isEmpty() && waiting == 0
    Card {
        RowLink(onOpen, {
            Text(when { waiting > 0 -> "$waiting file${if (waiting == 1) "" else "s"} waiting to publish"; ok -> "Records are up to date"; else -> "Records due: ${late.size}" },
                style = T.bodyBold, color = Brand.text)
            Text(if (late.isEmpty()) "Thanks for sending them." else late.joinToString(" · ") { it.text }, style = T.footnote, color = Brand.secondary, maxLines = 2)
        }) {}
    }
}

@Composable
fun RecordsScreen(model: StaffModel, onSend: () -> Unit, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val clip = LocalClipboardManager.current
    var confirm by remember { mutableStateOf<StaffRecordFile?>(null) }
    var err by remember { mutableStateOf<String?>(null) }
    if (model.workspaceId == null) return Sub("Send records", onBack) { Text("Pick a government from the menu on the home screen first.", style = T.subhead, color = Brand.secondary) }
    Sub("Send records", onBack) {
        if (model.can("submit")) PrimaryButton("Send a file", icon = Icons.Filled.Upload, onClick = onSend)
        val s = model.submissions
        if (s == null) { ErrorLine(model.error); return@Sub }
        Column {
            Eyebrow("What's due")
            Divided(s.due.size) { i -> DueRow(s.due[i]) }
        }
        s.address?.let { addr ->
            Column {
                Eyebrow("Email files to")
                Card { RowLink({ clip.setText(AnnotatedString(addr)) }, { Text(addr, style = T.bodyBold, color = Brand.navy); Text("Tap to copy", style = T.caption, color = Brand.secondary) }) }
                Text("Send from your work email. Emailed files wait here until someone checks them and presses Publish.",
                    style = T.footnote, color = Brand.secondary, modifier = Modifier.padding(top = 8.dp))
            }
        }
        Column {
            Eyebrow("Files sent")
            if (s.files.isEmpty()) Card { Text("Nothing sent yet.", style = T.subhead, color = Brand.secondary, modifier = Modifier.padding(14.dp)) }
            else Divided(s.files.size) { i ->
                val f = s.files[i]
                FileRow(f, canAct = model.can("submit"),
                    onPublish = { scope.launch { err = model.publishRecords(f.id) } },
                    onWithdraw = { confirm = f })
            }
            Text("Payments to private people are listed without their names.", style = T.footnote, color = Brand.secondary, modifier = Modifier.padding(top = 8.dp))
        }
        ErrorLine(err)
    }
    confirm?.let { f ->
        AlertDialog(onDismissRequest = { confirm = null },
            title = { Text(if (f.canPublish) "Discard this file?" else "Take these records off the site?") },
            text = { Text("The file stays on record. You can send a corrected one any time.") },
            confirmButton = { TextButton({ confirm = null; scope.launch { err = model.withdrawRecords(f.id) } }) { Text(if (f.canPublish) "Discard" else "Withdraw", color = Brand.salmon) } },
            dismissButton = { TextButton({ confirm = null }) { Text("Keep it") } })
    }
}

@Composable
private fun DueRow(d: StaffSubmissions.Due) {
    Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 14.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(if (d.current) Icons.Filled.CheckCircle else Icons.Filled.Schedule, null, tint = if (d.current) Brand.good else Brand.amber, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(12.dp))
        Column {
            Text(d.label, style = T.bodyBold, color = Brand.text)
            Text(if (d.current) (if (d.kind == "contracts") "Sent ${Staff.whenOf(d.have)}" else "In, through ${Staff.whenOf(d.have)}") else "Due: ${d.text}",
                style = T.caption, color = Brand.secondary)
        }
    }
}

@Composable
private fun FileRow(f: StaffRecordFile, canAct: Boolean, onPublish: () -> Unit, onWithdraw: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(f.name, style = T.bodyBold, color = Brand.text, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            Spacer(Modifier.width(8.dp))
            Chip(f.statusLabel, when (f.status) { "published" -> Brand.good; "waiting", "held" -> Brand.amber; else -> Brand.secondary })
        }
        Text(f.detail, style = T.caption, color = Brand.secondary)
        Text(listOfNotNull(if (f.via == "email") "Emailed" else "Sent", f.sentBy?.let { "by $it" }, f.sentAt?.let { Staff.whenOf(it) }).joinToString(" "),
            style = T.caption, color = Brand.secondary)
        if (f.status == "held") f.problem?.let { Text(it, style = T.caption, color = Brand.salmon) }
        if (canAct && (f.canPublish || f.canWithdraw)) Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            if (f.canPublish) TextButton(onPublish) { Text("Publish", color = Brand.navy) }
            if (f.canWithdraw) TextButton(onWithdraw) { Text(if (f.canPublish) "Discard" else "Withdraw", color = Brand.salmon) }
        }
    }
}

/** Pick the kind, pick the file, check what we read, publish. */
@Composable
fun SendFileScreen(model: StaffModel, demoPreview: Boolean, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var kind by remember { mutableStateOf("contracts") }
    var busy by remember { mutableStateOf(false) }
    val demoFill = demoPreview && model.demo != null
    var fileName by remember { mutableStateOf(if (demoFill) "contracts-oct-2026.xlsx" else null) }
    var preview by remember { mutableStateOf(if (demoFill) model.demoPreview("contracts") else null) }
    var err by remember { mutableStateOf<String?>(null) }
    var done by remember { mutableStateOf<String?>(null) }

    fun read(uri: Uri) {
        err = null
        val name = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst()) c.getString(0) else null
        } ?: "records.csv"
        fileName = name
        busy = true
        scope.launch {
            try {
                val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: throw IllegalStateException("Couldn't open that file.")
                preview = model.previewRecords(kind, name, bytes)
            } catch (e: Exception) { err = e.message } finally { busy = false }
        }
    }
    // No result registry outside an Activity (JVM screenshot tests): show the screen without a working picker.
    val picker = if (LocalActivityResultRegistryOwner.current != null)
        rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(::read) } else null

    Sub("Send a file", onBack) {
        val p = preview
        when {
            done != null -> Card {
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.CheckCircle, null, tint = Brand.good); Spacer(Modifier.width(10.dp))
                    Text(done ?: "", style = T.bodyBold, color = Brand.text)
                }
            }
            p != null -> {
                Column {
                    Eyebrow("What we read")
                    Card {
                        Detail("File", fileName ?: "")
                        Detail("Kind", Staff.recordKindLabel(p.kind))
                        p.rowCount?.let { Detail("Rows to publish", NumberFormat.getIntegerInstance(Locale.US).format(it)) }
                        p.parsedTotal?.let { Detail("Total", NumberFormat.getCurrencyInstance(Locale.US).apply { maximumFractionDigits = 0 }.format(it)) }
                        val s = p.period?.start; val e = p.period?.end
                        if (s != null && e != null) Detail("Dates", "${Staff.whenOf(s)} to ${Staff.whenOf(e)}")
                        p.alreadyOnSite?.takeIf { it > 0 }?.let { Detail("Already on site", "$it skipped") }
                        p.skipped?.takeIf { it > 0 }?.let { Detail("Rows skipped", "$it") }
                        p.withheld?.takeIf { it > 0 }?.let { Detail("Names withheld", "$it private people") }
                    }
                    Text(p.problem ?: "Check these match your report. Publishing puts them on BayCounty.me.", style = T.footnote,
                        color = if (p.ok) Brand.secondary else Brand.salmon, modifier = Modifier.padding(top = 8.dp))
                    p.warnings.orEmpty().forEach { Text(it, style = T.footnote, color = Brand.amber, modifier = Modifier.padding(top = 4.dp)) }
                }
                if (p.ok) PrimaryButton(if (busy) "Publishing…" else "Publish", enabled = !busy) {
                    busy = true
                    scope.launch {
                        err = model.publishRecords(p.id); busy = false
                        if (err == null) done = p.rowCount?.let { "Published $it row${if (it == 1) "" else "s"}." } ?: "Published."
                    }
                }
                QuietButton(if (p.ok) "Not now (keep it waiting)" else "Choose a different file") { preview = null; err = null }
            }
            else -> {
                Column {
                    Eyebrow("What are you sending?")
                    Card {
                        Staff.recordKinds.forEach { (k, label, _) ->
                            Row(Modifier.fillMaxWidth().clickable { kind = k }.heightIn(min = 52.dp).padding(horizontal = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                                RadioButton(kind == k, { kind = k }, colors = RadioButtonDefaults.colors(selectedColor = Brand.navy))
                                Text(label, style = T.body, color = Brand.text)
                            }
                        }
                    }
                    Text(Staff.recordKinds.first { it.first == kind }.third, style = T.footnote, color = Brand.secondary, modifier = Modifier.padding(top = 8.dp))
                }
                PrimaryButton(if (busy) "Reading ${fileName ?: "the file"}…" else "Choose a file", enabled = !busy) {
                    picker?.launch(arrayOf("text/csv", "text/comma-separated-values", "text/plain", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"))
                }
                Text("Excel or CSV, up to 3 MB. Nothing is published until you check it.", style = T.footnote, color = Brand.secondary)
            }
        }
        ErrorLine(err)
    }
}
