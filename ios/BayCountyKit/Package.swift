// swift-tools-version:5.9
// BayCountyKit: the app's data layer (models, BayCounty.me client, formatting).
// Foundation only, so it builds and tests on Linux as well as iOS.
import PackageDescription

let package = Package(
    name: "BayCountyKit",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "BayCountyKit", targets: ["BayCountyKit"])],
    targets: [
        .target(name: "BayCountyKit"),
        .testTarget(name: "BayCountyKitTests", dependencies: ["BayCountyKit"]),
    ]
)
