import XCTest

/// Taps each tile on the Living here tab and checks it opens its own screen, one level deep.
final class HomeTileTests: XCTestCase {
    let rows: [(row: String, title: String)] = [
        ("Things to do", "Events"),
        ("Beaches", "Beaches"),
        ("Parks and trails", "Parks"),
        ("Schools", "Schools"),
        ("Storms and alerts", "Emergencies"),
    ]

    func testEachLivingHereTileOpensItsOwnScreen() {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.tabBars.buttons["Living here"].waitForExistence(timeout: 8))
        app.tabBars.buttons["Living here"].tap()
        XCTAssertTrue(app.navigationBars["Living here"].waitForExistence(timeout: 8))
        for r in rows {
            let button = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", r.row)).firstMatch
            var tries = 0
            while !(button.exists && button.isHittable) && tries < 10 { app.swipeUp(); tries += 1 }
            XCTAssertTrue(button.isHittable, "Row \(r.row) not found")
            button.tap()
            XCTAssertTrue(app.navigationBars[r.title].waitForExistence(timeout: 8),
                          "\(r.row) should open \(r.title); nav bars: \(app.navigationBars.allElementsBoundByIndex.map(\.identifier))")
            // One back tap returns to Living here, so only one screen was pushed.
            app.navigationBars.buttons.element(boundBy: 0).tap()
            XCTAssertTrue(app.navigationBars["Living here"].waitForExistence(timeout: 5), "Back from \(r.title) should land on Living here")
        }
    }

    func testSearchButtonOpensSearch() {
        let app = XCUIApplication()
        app.launch()
        let field = app.navigationBars["Today"].buttons["Search"].firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 8))
        field.tap()
        XCTAssertTrue(app.navigationBars["Search"].waitForExistence(timeout: 5))
    }

    func testFiveTabs() {
        let app = XCUIApplication()
        app.launch()
        for t in ["Today", "Living here", "Money", "Government", "Search"] { XCTAssertTrue(app.tabBars.buttons[t].waitForExistence(timeout: 5), "Tab \(t)") }
    }
}
