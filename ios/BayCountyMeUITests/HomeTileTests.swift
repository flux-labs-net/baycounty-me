import XCTest

/// Taps each row of Today's Browse list and checks it opens its own screen, one level deep.
final class HomeTileTests: XCTestCase {
    let rows: [(row: String, title: String)] = [
        ("CRA spending", "CRA Spending"),
        ("Contracts", "Contracts"),
        ("How they voted", "Recorded votes"),
        ("Companies", "Companies"),
        ("Campaign money", "Campaign finance totals"),
        ("Glossary", "Glossary"),
    ]

    func testEachBrowseRowOpensItsOwnScreen() {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.navigationBars["Today"].waitForExistence(timeout: 8))
        for r in rows {
            let button = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", r.row)).firstMatch
            var tries = 0
            while !(button.exists && button.isHittable) && tries < 10 { app.swipeUp(); tries += 1 }
            XCTAssertTrue(button.isHittable, "Row \(r.row) not found")
            button.tap()
            XCTAssertTrue(app.navigationBars[r.title].waitForExistence(timeout: 8),
                          "\(r.row) should open \(r.title); nav bars: \(app.navigationBars.allElementsBoundByIndex.map(\.identifier))")
            // One back tap returns to Today, so only one screen was pushed.
            app.navigationBars.buttons.element(boundBy: 0).tap()
            XCTAssertTrue(app.navigationBars["Today"].waitForExistence(timeout: 5), "Back from \(r.title) should land on Today")
        }
    }

    func testSearchFieldOpensSearch() {
        let app = XCUIApplication()
        app.launch()
        let field = app.buttons["Search"].firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 8))
        field.tap()
        XCTAssertTrue(app.navigationBars["Search"].waitForExistence(timeout: 5))
    }

    func testFiveTabs() {
        let app = XCUIApplication()
        app.launch()
        for t in ["Today", "Living here", "Money", "Who decides", "Search"] { XCTAssertTrue(app.tabBars.buttons[t].waitForExistence(timeout: 5), "Tab \(t)") }
    }
}
