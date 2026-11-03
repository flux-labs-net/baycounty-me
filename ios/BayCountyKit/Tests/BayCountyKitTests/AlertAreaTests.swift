import XCTest
@testable import BayCountyKit

/// The maps government staff draw on alerts (site/area_map.js): pins with a circle, street lines and areas.
final class AlertAreaTests: XCTestCase {
    let drawn = #"{"type":"FeatureCollection","features":["#
        + #"{"type":"Feature","properties":{"radius_m":250},"geometry":{"type":"Point","coordinates":[-85.65,30.24]}},"#
        + #"{"type":"Feature","properties":{},"geometry":{"type":"LineString","coordinates":[[-85.66,30.25],[-85.64,30.25]]}},"#
        + #"{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[-85.7,30.2],[-85.6,30.2],[-85.6,30.3],[-85.7,30.2]]]}}]}"#

    func testParsesPinsLinesAndAreas() throws {
        let a = try XCTUnwrap(AlertArea.parse(drawn))
        XCTAssertEqual(a.shapes.count, 3)
        XCTAssertEqual(a.shapes[0], .pin(.init(lat: 30.24, lng: -85.65), radius: 250))
        guard case .line(let l) = a.shapes[1] else { return XCTFail("line") }
        XCTAssertEqual(l.count, 2)
        guard case .area(let rings) = a.shapes[2] else { return XCTFail("area") }
        XCTAssertEqual(rings.first?.count, 4)
        let b = try XCTUnwrap(a.bounds)
        XCTAssertEqual(b.south, 30.2, accuracy: 1e-9)
        XCTAssertEqual(b.north, 30.3, accuracy: 1e-9)
        XCTAssertEqual(b.west, -85.7, accuracy: 1e-9)
    }

    func testNothingToDraw() {
        XCTAssertNil(AlertArea.parse(nil))
        XCTAssertNil(AlertArea.parse(""))
        XCTAssertNil(AlertArea.parse("not json"))
        XCTAssertNil(AlertArea.parse(#"{"type":"FeatureCollection","features":[]}"#))
    }

    func testFirstMappedNotice() {
        let plain = Row(id: 0, values: ["title": .string("Flood Advisory")])
        let mapped = Row(id: 1, values: ["title": .string("Boil water"), "geometry": .string(drawn)])
        XCTAssertEqual(AlertArea.firstMapped([plain, mapped])?.notice.string("title"), "Boil water")
        XCTAssertNil(AlertArea.firstMapped([plain]))
    }

    func testPinsFromTheStaffApp() throws {
        XCTAssertNil(AlertArea.pinsGeoJSON([], radius: 250))
        let g = try XCTUnwrap(AlertArea.pinsGeoJSON([.init(lat: 30.24, lng: -85.65)], radius: 250))
        XCTAssertEqual(AlertArea.parse(g)?.shapes, [.pin(.init(lat: 30.24, lng: -85.65), radius: 250)])
        XCTAssertEqual(AlertArea.parse(AlertArea.pinsGeoJSON([.init(lat: 30.24, lng: -85.65)], radius: nil))?.shapes, [.pin(.init(lat: 30.24, lng: -85.65), radius: nil)])
    }

    func testPlacedRoadMapsSaySo() throws {
        let g = #"{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"placed":"street-names"},"geometry":{"type":"LineString","coordinates":[[-85.708441,30.187998],[-85.708537,30.184905]]}}]}"#
        let a = try XCTUnwrap(AlertArea.parse(g))
        XCTAssertEqual(a.placed, "street-names")
        XCTAssertEqual(a.note, "Placed on the map from the streets the notice names. Check the notice for the exact spot.")
        XCTAssertNil(AlertArea.parse(#"{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[-85.6,30.2]}}]}"#)?.note)
    }
}
