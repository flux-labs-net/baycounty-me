import XCTest
@testable import BayCountyKit

/// Gift dates measured from the vote, so a gift before the vote never reads as one after it.
final class GiftTimingTests: XCTestCase {
    func testOneGiftBeforeTheVote() {
        XCTAssertEqual(MoneyMap.giftWhen(["2024-03-04"], voteDate: "2026-06-16"), "on Mar 4, 2024, 834 days before the vote")
    }

    func testSameDayAndOneDay() {
        XCTAssertEqual(MoneyMap.giftWhen(["2026-06-16"], voteDate: "2026-06-16"), "on Jun 16, 2026, the same day as the vote")
        XCTAssertEqual(MoneyMap.giftWhen(["2026-06-17"], voteDate: "2026-06-16"), "on Jun 17, 2026, 1 day after the vote")
    }

    func testGiftsOnBothSides() {
        XCTAssertEqual(MoneyMap.giftWhen(["2026-06-17", "2024-03-04", "2026-06-17"], voteDate: "2026-06-16"),
                       "on Mar 4, 2024 (834 days before the vote) and Jun 17, 2026 (1 day after)")
    }

    func testNoDatesSaysNothing() {
        XCTAssertEqual(MoneyMap.giftWhen(nil, voteDate: "2026-06-16"), "")
    }
}
