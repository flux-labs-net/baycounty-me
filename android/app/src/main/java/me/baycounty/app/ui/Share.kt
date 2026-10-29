package me.baycounty.app.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.widget.Toast
import androidx.compose.foundation.layout.Box
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext

/*
 * Copy and Share for one record or page (RecordShare in the kit, the same text as the website's Share button):
 * copy the link, or open the share sheet with the link.
 */

fun copyToClipboard(context: Context, label: String, text: String) {
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText(label, text))
    // Android 13 and later show their own "Copied" confirmation
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) Toast.makeText(context, "Copied", Toast.LENGTH_SHORT).show()
}

fun openShareSheet(context: Context, subject: String, text: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_SUBJECT, subject).putExtra(Intent.EXTRA_TEXT, text)
    context.startActivity(Intent.createChooser(send, null).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}

/** The menu itself: Copy link and Share. Share sends the link (the app it goes to draws the preview card from it);
 *  a record with no link shares its text instead. */
@Composable
fun ShareDropdown(expanded: Boolean, onDismiss: () -> Unit, subject: String, text: () -> String, url: String?) {
    val context = LocalContext.current
    DropdownMenu(expanded = expanded, onDismissRequest = onDismiss, containerColor = Brand.surface) {
        if (url != null) DropdownMenuItem(text = { Text("Copy link", style = T.body, color = Brand.text) },
            leadingIcon = { Icon(icon("link"), null, tint = Brand.navy) },
            onClick = { onDismiss(); copyToClipboard(context, subject, url) })
        DropdownMenuItem(text = { Text("Share…", style = T.body, color = Brand.text) },
            leadingIcon = { Icon(icon("square.and.arrow.up"), null, tint = Brand.navy) },
            onClick = { onDismiss(); openShareSheet(context, subject, url ?: text()) })
    }
}

/** A top-bar share icon that opens the menu. */
@Composable
fun ShareMenuButton(subject: String, url: String?, text: () -> String) {
    var open by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick = { open = true }) { Icon(icon("square.and.arrow.up"), "Share", tint = Brand.navy) }
        ShareDropdown(open, { open = false }, subject, text, url)
    }
}
