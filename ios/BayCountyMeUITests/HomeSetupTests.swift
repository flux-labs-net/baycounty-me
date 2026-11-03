import XCTest

/// First launch asks where you live and whether you own or rent; renters' Home tab leads with utilities.
final class HomeSetupTests: XCTestCase {
    func testRenterSetupLeadsWithUtilities() {
        let app = XCUIApplication()
        app.launchArguments += ["-setupSeen", "NO"]
        app.launch()
        XCTAssertTrue(app.staticTexts["Where do you live?"].waitForExistence(timeout: 8))
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH %@", "I rent")).firstMatch.tap()
        app.buttons["setupContinue"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["tile-utilities"].waitForExistence(timeout: 8), "Renters' Home tab should lead with utilities")
        XCTAssertFalse(app.descendants(matching: .any)["tile-tax"].exists)
    }
}
