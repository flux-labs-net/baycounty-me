package me.baycounty.kit

import org.junit.Assert.assertEquals
import org.junit.Test

/** Gift dates measured from the vote, so a gift before the vote never reads as one after it. */
class GiftTimingTest {
    @Test fun oneGiftBeforeTheVote() =
        assertEquals("on Mar 4, 2024, 834 days before the vote", MoneyMap.giftWhen(listOf("2024-03-04"), "2026-06-16"))

    @Test fun sameDayAndOneDay() {
        assertEquals("on Jun 16, 2026, the same day as the vote", MoneyMap.giftWhen(listOf("2026-06-16"), "2026-06-16"))
        assertEquals("on Jun 17, 2026, 1 day after the vote", MoneyMap.giftWhen(listOf("2026-06-17"), "2026-06-16"))
    }

    @Test fun giftsOnBothSides() = assertEquals(
        "on Mar 4, 2024 (834 days before the vote) and Jun 17, 2026 (1 day after)",
        MoneyMap.giftWhen(listOf("2026-06-17", "2024-03-04", "2026-06-17"), "2026-06-16"),
    )

    @Test fun noDatesSaysNothing() = assertEquals("", MoneyMap.giftWhen(null, "2026-06-16"))
}
