import XCTest

/// The tax calculator's assessed value uses a number pad, which has no return key.
/// A Done button above the keyboard must close it, and the estimate must follow the new value.
final class NumberPadDoneTests: XCTestCase {
    func testDoneClosesTheNumberPad() throws {
        let app = XCUIApplication()
        app.launchArguments += ["-screen", "tax"]
        app.launch()
        let field = app.textFields["assessedValue"]
        XCTAssertTrue(field.waitForExistence(timeout: 15), "Assessed value field not found")

        // Tap the right end so the cursor lands after the digits, then clear and type a new value.
        field.coordinate(withNormalizedOffset: CGVector(dx: 0.97, dy: 0.5)).tap()
        // One delete at a time: the field re-adds commas after each change, which can move the cursor.
        for _ in 0..<20 {
            let v = (field.value as? String) ?? ""
            if !v.contains(where: \.isNumber) { break }
            field.typeText(XCUIKeyboardKey.delete.rawValue)
        }
        field.typeText("400000")
        XCTAssertEqual(field.value as? String, "400,000")

        let done = app.toolbars.buttons["Done"].exists ? app.toolbars.buttons["Done"] : app.buttons["Done"]
        XCTAssertTrue(done.waitForExistence(timeout: 5), "No Done button above the number pad")
        XCTAssertTrue(app.keyboards.firstMatch.exists, "Number pad should be open")
        save(app, "keypad-open")

        done.tap()
        let gone = NSPredicate(format: "exists == false")
        expectation(for: gone, evaluatedWith: app.keyboards.firstMatch)
        waitForExpectations(timeout: 5)
        XCTAssertEqual(field.value as? String, "400,000")
        save(app, "keypad-closed")
    }

    /// Screenshots for the PR: kept on the test run and written where CI uploads them.
    private func save(_ app: XCUIApplication, _ name: String) {
        let shot = app.screenshot()
        let a = XCTAttachment(screenshot: shot); a.name = name; a.lifetime = .keepAlways; add(a)
        let dir = URL(fileURLWithPath: "/tmp/ui-shots")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try? shot.pngRepresentation.write(to: dir.appendingPathComponent("\(name).png"))
    }
}
