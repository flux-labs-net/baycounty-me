import XCTest

/// Taps each "Follow the money" tile on Home and checks it opens its own screen, one level deep.
/// (When the tiles were links in one list row, every tap opened the Glossary.)
final class HomeTileTests: XCTestCase {
    let tiles: [(tile: String, title: String)] = [
        ("Tax calculator", "Tax Dollars"),
        ("CRA Spending", "CRA Spending"),
        ("Contracts", "Contracts"),
        ("How They Voted", "Recorded votes"),
        ("Companies", "Companies"),
        ("Campaign Money", "Campaign finance totals"),
        ("Amendment 3", "Amendment 3"),
        ("Glossary", "Glossary"),
    ]

    func testEachTileOpensItsOwnScreen() {
        let app = XCUIApplication()
        app.launch()
        for t in tiles {
            let button = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", t.tile)).firstMatch
            var tries = 0
            while !(button.exists && button.isHittable) && tries < 8 { app.swipeUp(); tries += 1 }
            XCTAssertTrue(button.isHittable, "Tile \(t.tile) not found")
            button.tap()
            XCTAssertTrue(app.navigationBars[t.title].waitForExistence(timeout: 8),
                          "\(t.tile) should open \(t.title); nav bars: \(app.navigationBars.allElementsBoundByIndex.map(\.identifier))")
            // One back tap returns Home, so only one screen was pushed.
            app.navigationBars.buttons.element(boundBy: 0).tap()
            XCTAssertTrue(app.navigationBars["BayCounty.me"].waitForExistence(timeout: 5), "Back from \(t.title) should land on Home")
        }
    }
}
