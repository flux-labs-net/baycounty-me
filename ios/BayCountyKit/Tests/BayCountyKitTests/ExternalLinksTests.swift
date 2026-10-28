import XCTest
@testable import BayCountyKit

final class ExternalLinksTests: XCTestCase {
    func testDirectionsOpenInMaps() throws {
        let row = Row(id: 1, values: ["name": .string("Frank Brown Park"), "latitude": .number(30.21), "longitude": .number(-85.87)])
        let url = try XCTUnwrap(Outdoors.directions(row))
        XCTAssertTrue(ExternalLinks.opensOutsideApp(url))
    }

    func testWebPagesStayInApp() {
        XCTAssertFalse(ExternalLinks.opensOutsideApp(URL(string: "https://baycounty.me/parks")!))
        XCTAssertFalse(ExternalLinks.opensOutsideApp(URL(string: "https://www.google.com/search?q=x")!))
        XCTAssertTrue(ExternalLinks.opensOutsideApp(URL(string: "maps://?q=City%20Hall")!))
        XCTAssertTrue(ExternalLinks.opensOutsideApp(URL(string: "tel:8502485000")!))
        XCTAssertTrue(ExternalLinks.opensOutsideApp(URL(string: "https://www.google.com/maps/dir/?api=1&destination=1,2")!))
    }
}
