import XCTest

/// Taps cards in each section of the Money tab and checks each opens its own screen, one level deep.
final class MoneyTabTests: XCTestCase {
    let cards: [(card: String, title: String)] = [
        ("Tax calculator", "Tax Dollars"),
        ("Fees on your tax bill", "Fees on tax bills"),
        ("Budgets", "Budgets by fund and department"),
        ("CRA spending", "CRA Spending"),
        ("Contracts", "Contracts"),
        ("Debt", "Debt by government"),
        ("Audit findings", "Audit findings"),
        ("2026 candidates", "2026 local candidates"),
    ]

    func testEachCardOpensItsOwnScreen() {
        let app = XCUIApplication()
        app.launch()
        app.tabBars.buttons["Money"].tap()
        XCTAssertTrue(app.navigationBars["Public Money"].waitForExistence(timeout: 5))
        for c in cards {
            let card = app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", c.card)).firstMatch
            var tries = 0
            while !(card.exists && card.isHittable) && tries < 10 { app.swipeUp(); tries += 1 }
            XCTAssertTrue(card.isHittable, "Card \(c.card) not found")
            card.tap()
            XCTAssertTrue(app.navigationBars[c.title].waitForExistence(timeout: 8),
                          "\(c.card) should open \(c.title); nav bars: \(app.navigationBars.allElementsBoundByIndex.map(\.identifier))")
            app.navigationBars.buttons.element(boundBy: 0).tap()
            XCTAssertTrue(app.navigationBars["Public Money"].waitForExistence(timeout: 5), "Back from \(c.title) should land on Public Money")
        }
    }
}
