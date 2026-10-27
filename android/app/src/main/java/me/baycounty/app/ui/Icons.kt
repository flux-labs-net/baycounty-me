package me.baycounty.app.ui

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FilterAlt
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material.icons.automirrored.outlined.CompareArrows
import androidx.compose.material.icons.automirrored.outlined.List
import androidx.compose.material.icons.automirrored.outlined.MenuBook
import androidx.compose.material.icons.automirrored.outlined.ShowChart
import androidx.compose.material.icons.automirrored.outlined.TrendingUp
import androidx.compose.material.icons.outlined.*
import androidx.compose.ui.graphics.vector.ImageVector

/** SF Symbol names (shared with iOS and the kit's dataset specs) mapped to Material icons. */
fun icon(symbol: String?): ImageVector = when (symbol) {
    "house", "house.fill" -> Icons.Outlined.Home
    "house.slash" -> Icons.Outlined.HomeWork
    "mappin.and.ellipse", "location" -> Icons.Outlined.Place
    "map" -> Icons.Outlined.Map
    "square.and.arrow.up" -> Icons.Outlined.Share
    "dollarsign.circle", "dollarsign.arrow.circlepath" -> Icons.Outlined.Paid
    "calendar", "calendar.badge.clock" -> Icons.Outlined.CalendarMonth
    "calendar.badge.plus" -> Icons.Outlined.EditCalendar
    "magnifyingglass" -> Icons.Outlined.Search
    "percent" -> Icons.Outlined.Percent
    "doc.plaintext", "doc", "doc.text", "doc.on.doc" -> Icons.Outlined.Description
    "doc.text.magnifyingglass" -> Icons.Outlined.FindInPage
    "doc.questionmark", "questionmark.circle.fill" -> Icons.Outlined.HelpOutline
    "doc.badge.plus" -> Icons.Outlined.NoteAdd
    "bed.double" -> Icons.Outlined.Hotel
    "chart.pie" -> Icons.Outlined.PieChart
    "chart.bar", "chart.bar.xaxis" -> Icons.Outlined.BarChart
    "chart.line.uptrend.xyaxis" -> Icons.AutoMirrored.Outlined.TrendingUp
    "checkmark.rectangle", "checkmark.circle" -> Icons.Outlined.CheckCircle
    "gauge.with.dots.needle.33percent" -> Icons.Outlined.Speed
    "person.2", "person.3" -> Icons.Outlined.Groups
    "person", "person.crop.circle", "person.crop.square" -> Icons.Outlined.Person
    "person.text.rectangle" -> Icons.Outlined.Badge
    "person.crop.circle.badge.checkmark" -> Icons.Outlined.HowToReg
    "person.badge.clock" -> Icons.Outlined.History
    "building.2", "building" -> Icons.Outlined.Business
    "storefront" -> Icons.Outlined.Storefront
    "graduationcap" -> Icons.Outlined.School
    "star" -> Icons.Outlined.StarOutline
    "xmark.circle" -> Icons.Outlined.HighlightOff
    "bolt" -> Icons.Outlined.Bolt
    "phone" -> Icons.Outlined.Phone
    "drop" -> Icons.Outlined.WaterDrop
    "trash" -> Icons.Outlined.Delete
    "fork.knife" -> Icons.Outlined.Restaurant
    "hand.raised" -> Icons.Outlined.VolunteerActivism
    "sun.max" -> Icons.Outlined.WbSunny
    "repeat" -> Icons.Outlined.Repeat
    "building.columns" -> Icons.Outlined.AccountBalance
    "checkmark.seal" -> Icons.Outlined.Verified
    "road.lanes" -> Icons.Outlined.AddRoad
    "hurricane" -> Icons.Outlined.Cyclone
    "signature" -> Icons.Outlined.Draw
    "arrow.triangle.2.circlepath", "arrow.clockwise" -> Icons.Outlined.Sync
    "exclamationmark.triangle" -> Icons.Outlined.WarningAmber
    "exclamationmark.circle", "exclamationmark.bubble" -> Icons.Outlined.ErrorOutline
    "checklist" -> Icons.Outlined.Checklist
    "hand.raised" -> Icons.Outlined.PanTool
    "creditcard" -> Icons.Outlined.CreditCard
    "banknote" -> Icons.Outlined.Payments
    "heart.text.square", "heart" -> Icons.Outlined.VolunteerActivism
    "gift" -> Icons.Outlined.CardGiftcard
    "briefcase" -> Icons.Outlined.Work
    "envelope", "envelope.open" -> Icons.Outlined.Email
    "clock", "clock.arrow.circlepath" -> Icons.Outlined.Schedule
    "link" -> Icons.Outlined.Link
    "point.3.connected.trianglepath.dotted", "point.3.filled.connected.trianglepath.dotted", "circle.hexagongrid" -> Icons.Outlined.Hub
    "arrow.right" -> Icons.AutoMirrored.Outlined.ArrowForward
    "arrow.left.arrow.right" -> Icons.AutoMirrored.Outlined.CompareArrows
    "arrow.up.right" -> Icons.Outlined.NorthEast
    "arrow.down.left" -> Icons.Outlined.SouthWest
    "arrow.down.circle" -> Icons.Outlined.Download
    "book", "text.book.closed", "character.book.closed" -> Icons.AutoMirrored.Outlined.MenuBook
    "sparkles" -> Icons.Outlined.AutoAwesome
    "list.bullet", "list.bullet.rectangle" -> Icons.AutoMirrored.Outlined.List
    "tablecells" -> Icons.Outlined.TableChart
    "square.grid.2x2" -> Icons.Outlined.GridView
    "tray.2", "tray.full" -> Icons.Outlined.Inventory2
    "bell" -> Icons.Outlined.Notifications
    "bubble.left", "bubble.left.and.text.bubble.right", "questionmark.bubble", "checkmark.bubble" -> Icons.Outlined.Forum
    "megaphone" -> Icons.Outlined.Campaign
    "info.circle" -> Icons.Outlined.Info
    "lightbulb" -> Icons.Outlined.Lightbulb
    "flag" -> Icons.Outlined.Flag
    "safari" -> Icons.Outlined.Public
    "curlybraces" -> Icons.Outlined.Code
    "wifi.slash" -> Icons.Outlined.WifiOff
    "minus.circle" -> Icons.Outlined.RemoveCircleOutline
    "line.3.horizontal.decrease.circle" -> Icons.Outlined.FilterAlt
    "line.3.horizontal.decrease.circle.fill" -> Icons.Filled.FilterAlt
    "xmark", "xmark.circle.fill" -> Icons.Outlined.Close
    "chevron.right" -> Icons.Outlined.ChevronRight
    "chevron.down" -> Icons.Outlined.ExpandMore
    "chevron.up" -> Icons.Outlined.ExpandLess
    "chevron.up.chevron.down" -> Icons.Outlined.UnfoldMore
    "checkmark" -> Icons.Outlined.Check
    "trend" -> Icons.AutoMirrored.Outlined.ShowChart
    "globe" -> Icons.Outlined.Public
    "beach.umbrella" -> Icons.Outlined.BeachAccess
    "tree" -> Icons.Outlined.Park
    "drop" -> Icons.Outlined.WaterDrop
    "water.waves" -> Icons.Outlined.Waves
    "wind" -> Icons.Outlined.Air
    "thermometer.medium" -> Icons.Outlined.Thermostat
    "sailboat" -> Icons.Outlined.Sailing
    "figure.hiking" -> Icons.Outlined.Hiking
    "figure.run" -> Icons.Outlined.SportsSoccer
    "figure.play" -> Icons.Outlined.Toys
    "parkingsign" -> Icons.Outlined.LocalParking
    "testtube.2" -> Icons.Outlined.Science
    "arrow.up.right.square" -> Icons.Outlined.Launch
    "arrow.triangle.turn.up.right.diamond" -> Icons.Outlined.Directions
    "car.side.arrowtriangle.up.fill" -> Icons.Outlined.DirectionsCar
    "cloud.bolt.rain" -> Icons.Outlined.Thunderstorm
    "house.lodge" -> Icons.Outlined.NightShelter
    "drop.triangle", "drop" -> Icons.Outlined.WaterDrop
    "phone" -> Icons.Outlined.Phone
    "house.and.flag" -> Icons.Outlined.Cottage
    "shield.lefthalf.filled" -> Icons.Outlined.Shield
    "bolt.trianglebadge.exclamationmark" -> Icons.Outlined.ElectricBolt
    "hammer" -> Icons.Outlined.Construction
    "bell.badge" -> Icons.Outlined.NotificationsActive
    "exclamationmark.octagon" -> Icons.Outlined.Report
    else -> Icons.Outlined.TableChart
}
