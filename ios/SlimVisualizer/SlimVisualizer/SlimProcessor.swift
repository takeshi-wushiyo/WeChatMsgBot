import UIKit
import Accelerate

/// Ports the Python sin²-tapered horizontal squeeze algorithm to Swift/vImage.
///
/// Algorithm (mirrors slim_visualizer.py):
///   1. Top `bodyStart` fraction of the image is left untouched (head area).
///   2. For each row in the body region, compute a per-row horizontal squeeze
///      factor using a sin⁰·⁵ taper so the effect is strongest at the torso
///      and fades smoothly near the head/neck and ankles.
///   3. Each row is resampled with nearest-neighbour mapping.
///   4. The result is lightly sharpened.
enum SlimProcessor {

    // MARK: - Constants (mirrors Python)

    private static let bodyStart: Double = 0.20
    private static let bodyEnd:   Double = 0.95

    // MARK: - Public API

    /// Applies the slim effect on a background thread and returns the result.
    /// Returns `nil` if the image cannot be processed.
    static func apply(to image: UIImage, slimPercent: Double) async -> UIImage? {
        guard slimPercent > 0 else { return image }
        return await Task.detached(priority: .userInitiated) {
            processSync(image: image, slimPercent: slimPercent)
        }.value
    }

    // MARK: - Core transform

    private static func processSync(image: UIImage, slimPercent: Double) -> UIImage? {
        guard let cgImage = image.cgImage else { return nil }

        let width  = cgImage.width
        let height = cgImage.height
        let bytesPerPixel = 4
        let bytesPerRow   = width * bytesPerPixel

        // ── Decode to RGBA byte buffer ──────────────────────────────────────
        guard let ctx = CGContext(
            data: nil,
            width: width, height: height,
            bitsPerComponent: 8,
            bytesPerRow: bytesPerRow,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else { return nil }

        ctx.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))

        guard let srcData = ctx.data else { return nil }
        let srcPtr = srcData.bindMemory(to: UInt8.self,
                                        capacity: height * bytesPerRow)

        // ── Allocate output buffer (copy of source) ─────────────────────────
        let dstBuffer = UnsafeMutablePointer<UInt8>.allocate(capacity: height * bytesPerRow)
        defer { dstBuffer.deallocate() }
        dstBuffer.initialize(from: srcPtr, count: height * bytesPerRow)

        // ── Row-wise squeeze ────────────────────────────────────────────────
        let slimFactor = slimPercent / 100.0
        let cx         = Double(width) / 2.0
        let startRow   = Int(Double(height) * bodyStart)
        let endRow     = Int(Double(height) * bodyEnd)
        let span       = Double(max(endRow - startRow - 1, 1))

        for row in startRow..<endRow {
            let t      = Double(row - startRow) / span
            let taper  = pow(sin(t * .pi), 0.5)
            let squeeze = 1.0 - slimFactor * taper  // > 0 always (slimFactor ≤ 0.5)

            let srcRowOffset = row * bytesPerRow
            let dstRowOffset = row * bytesPerRow

            for dstX in 0..<width {
                // Inverse mapping: dstX → srcX
                let srcXf  = cx + (Double(dstX) - cx) / squeeze
                let srcX   = max(0, min(Double(width - 1), srcXf))
                let srcXi  = Int(srcX)                    // nearest-neighbour

                let srcOff = srcRowOffset + srcXi * bytesPerPixel
                let dstOff = dstRowOffset + dstX  * bytesPerPixel

                dstBuffer[dstOff]     = srcPtr[srcOff]
                dstBuffer[dstOff + 1] = srcPtr[srcOff + 1]
                dstBuffer[dstOff + 2] = srcPtr[srcOff + 2]
                dstBuffer[dstOff + 3] = srcPtr[srcOff + 3]
            }
        }

        // ── Build CGImage from output buffer ────────────────────────────────
        guard let dstCtx = CGContext(
            data: dstBuffer,
            width: width, height: height,
            bitsPerComponent: 8,
            bytesPerRow: bytesPerRow,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ), let dstCGImage = dstCtx.makeImage() else { return nil }

        // ── Unsharp-mask sharpening (mirrors Python UnsharpMask) ────────────
        let sharpened = sharpen(cgImage: dstCGImage) ?? dstCGImage

        return UIImage(cgImage: sharpened,
                       scale: image.scale,
                       orientation: image.imageOrientation)
    }

    // MARK: - Sharpening with vImage

    /// Light unsharp-mask equivalent using vImage convolve.
    private static func sharpen(cgImage: CGImage) -> CGImage? {
        let width  = cgImage.width
        let height = cgImage.height
        let bytesPerRow = width * 4

        var src = vImage_Buffer()
        var dst = vImage_Buffer()

        guard
            vImageBuffer_InitWithCGImage(
                &src, &vImageConverterFormat,
                nil, cgImage, vImage_Flags(kvImageNoFlags)
            ) == kvImageNoError,
            vImageBuffer_Init(
                &dst,
                vImagePixelCount(height),
                vImagePixelCount(width),
                32,
                vImage_Flags(kvImageNoFlags)
            ) == kvImageNoError
        else { return nil }

        defer {
            free(src.data)
            free(dst.data)
        }

        // 3×3 unsharp-mask kernel (sharpen)
        // [ 0, -1,  0 ]
        // [-1,  5, -1 ]
        // [ 0, -1,  0 ]
        var kernel: [Int16] = [
             0, -1,  0,
            -1,  5, -1,
             0, -1,  0,
        ]
        let divisor: Int32 = 1

        let error = vImageConvolve_ARGB8888(
            &src, &dst, nil, 0, 0,
            &kernel, 3, 3,
            divisor,
            nil,
            vImage_Flags(kvImageEdgeExtend)
        )
        guard error == kvImageNoError else { return nil }

        var format = vImageConverterFormat
        return try? dst.createCGImage(format: format)
    }

    /// vImage format descriptor for ARGB8888.
    /// Uses `premultipliedLast` (RGBA) to match the CGContext bitmap format used
    /// during decoding, keeping alpha interpretation consistent throughout.
    private static var vImageConverterFormat: vImage_CGImageFormat = {
        vImage_CGImageFormat(
            bitsPerComponent: 8,
            bitsPerPixel: 32,
            colorSpace: nil,
            bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedLast.rawValue),
            version: 0,
            decode: nil,
            renderingIntent: .defaultIntent
        )
    }()
}
