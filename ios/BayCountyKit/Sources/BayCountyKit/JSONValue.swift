import Foundation

/// Any JSON value. Dataset rows are heterogeneous, so they're kept as `[String: JSONValue]`.
public enum JSONValue: Codable, Hashable, Sendable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case array([JSONValue])
    case object([String: JSONValue])
    case null

    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null; return }
        if let v = try? c.decode(Bool.self) { self = .bool(v); return }
        if let v = try? c.decode(Double.self) { self = .number(v); return }
        if let v = try? c.decode(String.self) { self = .string(v); return }
        if let v = try? c.decode([JSONValue].self) { self = .array(v); return }
        if let v = try? c.decode([String: JSONValue].self) { self = .object(v); return }
        throw DecodingError.dataCorruptedError(in: c, debugDescription: "Unsupported JSON value")
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        case .null: try c.encodeNil()
        }
    }

    public var isEmpty: Bool {
        switch self {
        case .null: return true
        case .string(let s): return s.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        case .array(let a): return a.isEmpty
        case .object(let o): return o.isEmpty
        default: return false
        }
    }

    public var stringValue: String? {
        switch self {
        case .string(let s): return s
        case .number(let n): return n == n.rounded() && abs(n) < 1e15 ? String(Int64(n)) : String(n)
        case .bool(let b): return b ? "true" : "false"
        default: return nil
        }
    }

    public var doubleValue: Double? {
        switch self {
        case .number(let n): return n
        case .string(let s): return Double(s.replacingOccurrences(of: ",", with: ""))
        default: return nil
        }
    }

    public var boolValue: Bool? {
        switch self {
        case .bool(let b): return b
        case .string(let s):
            switch s.lowercased() { case "true", "yes": return true; case "false", "no": return false; default: return nil }
        default: return nil
        }
    }

    public var arrayValue: [JSONValue]? {
        if case .array(let a) = self { return a }
        return nil
    }

    /// All text in the value, for search.
    public var searchText: String {
        switch self {
        case .string(let s): return s
        case .number, .bool: return stringValue ?? ""
        case .array(let a): return a.map(\.searchText).joined(separator: " ")
        case .object(let o): return o.values.map(\.searchText).joined(separator: " ")
        case .null: return ""
        }
    }
}

/// One record from a dataset.
public struct Row: Identifiable, Hashable, Sendable {
    public let id: Int
    public let values: [String: JSONValue]

    public init(id: Int, values: [String: JSONValue]) {
        self.id = id
        self.values = values
    }

    public subscript(key: String) -> JSONValue? { values[key] }

    public func string(_ key: String) -> String? {
        guard let v = values[key], !v.isEmpty else { return nil }
        return v.stringValue
    }

    public func number(_ key: String) -> Double? { values[key]?.doubleValue }
    public func bool(_ key: String) -> Bool? { values[key]?.boolValue }

    public func strings(_ key: String) -> [String] {
        values[key]?.arrayValue?.compactMap { $0.stringValue }.filter { !$0.isEmpty } ?? []
    }

    /// First non-empty string among keys.
    public func first(_ keys: [String]) -> String? {
        for k in keys { if let s = string(k) { return s } }
        return nil
    }

    /// First number among keys.
    public func firstNumber(_ keys: [String]) -> Double? {
        for k in keys { if let n = number(k) { return n } }
        return nil
    }

    public func url(_ key: String) -> URL? {
        guard let s = string(key), s.hasPrefix("http") else { return nil }
        return URL(string: s)
    }

    /// Lowercased text of every value, cached by the caller if needed.
    public var searchText: String {
        values.values.map(\.searchText).joined(separator: " ").lowercased()
    }

    public static func decodeList(_ data: Data) throws -> [Row] {
        let raw = try JSONDecoder().decode([[String: JSONValue]].self, from: data)
        return raw.enumerated().map { Row(id: $0.offset, values: $0.element) }
    }
}
