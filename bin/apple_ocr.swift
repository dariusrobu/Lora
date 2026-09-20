import Foundation
import Vision
import AppKit

var imageData: Data?
if CommandLine.arguments.count > 1 {
    let path = CommandLine.arguments[1]
    imageData = FileManager.default.contents(atPath: path)
} else {
    imageData = FileHandle.standardInput.readDataToEndOfFile()
}

guard let data = imageData, !data.isEmpty,
      let image = NSImage(data: data),
      let tiffData = image.tiffRepresentation,
      let ciImage = CIImage(data: tiffData) else {
    exit(0)
}

let request = VNRecognizeTextRequest { (req, err) in
    guard let observations = req.results as? [VNRecognizedTextObservation] else { return }
    
    // Sort observations strictly top-to-bottom (Y=1.0 is top in Apple Vision)
    // and left-to-right for items on the same horizontal line.
    let sorted = observations.sorted { (a, b) -> Bool in
        let yThreshold: CGFloat = 0.012 // lines within 1.2% vertical distance belong to the same row
        if abs(a.boundingBox.origin.y - b.boundingBox.origin.y) > yThreshold {
            return a.boundingBox.origin.y > b.boundingBox.origin.y
        }
        return a.boundingBox.origin.x < b.boundingBox.origin.x
    }
    
    // Group into visual lines
    var lines: [String] = []
    var currentLine: [VNRecognizedTextObservation] = []
    
    for obs in sorted {
        if let last = currentLine.last {
            if abs(last.boundingBox.origin.y - obs.boundingBox.origin.y) <= 0.015 {
                currentLine.append(obs)
            } else {
                let lineStr = currentLine.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "   ")
                lines.append(lineStr)
                currentLine = [obs]
            }
        } else {
            currentLine = [obs]
        }
    }
    if !currentLine.isEmpty {
        let lineStr = currentLine.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "   ")
        lines.append(lineStr)
    }
    
    print(lines.joined(separator: "\n"))
}

request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
if #available(macOS 13.0, *) {
    request.automaticallyDetectsLanguage = true
}

let handler = VNImageRequestHandler(ciImage: ciImage, options: [:])
try? handler.perform([request])
