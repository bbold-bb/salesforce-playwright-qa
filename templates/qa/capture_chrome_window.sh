#!/bin/zsh
# Full-resolution QA screenshot of the Chrome tab a test is running in, using macOS screencapture.
# For screenshots taken while you (or an AI assistant's browser tool) drive Chrome by hand. Browser tools'
# screenshots are downscaled; this saves the page at native Retina resolution. Playwright runs don't need it,
# since they save their own screenshots.
#
# Usage: capture_chrome_window.sh <out.png> <tab URL substring> [toolbar points] [x y w h]
#   capture_chrome_window.sh PROJ-17-S3.png <record Id from the tab's URL>
#   capture_chrome_window.sh PROJ-17-S3.png <record Id from the tab's URL> 88 0 0 1000 400
#
# What it does: brings the matching tab to the front of its window for about a second, captures that
# one window (never the whole screen), puts the window's previous tab back, then crops off Chrome's
# tab strip and toolbar so only the page shows.
#   toolbar points: height of Chrome's tab strip and toolbar, in points. Default 87 (the window's height
#     less the page's window.innerHeight; measure yours once if the crop is off). A debugging banner below
#     it is found and trimmed automatically.
#   x y w h: optional crop of the page, in CSS pixels from the page's top left (getBoundingClientRect).
#     Use it to keep anything that isn't test data, such as records copied from production, out of the image.
#
# Needs Screen Recording permission for the app running the shell (System Settings, Privacy & Security,
# Screen Recording), and Automation permission to control Google Chrome. Without Screen Recording, window
# titles read blank and no window is found. The window must be on screen and uncovered.

set -e
out=$1; want=$2; toolbar=${3:-87}
[[ -z $out || -z $want ]] && { echo "usage: $0 <out.png> <tab URL substring> [toolbar points] [x y w h]"; exit 2; }

# Bring the tab forward and remember what was showing.
info=$(osascript - "$want" <<'EOF'
on run argv
  set want to item 1 of argv
  tell application "Google Chrome"
    repeat with w in windows
      set i to 0
      repeat with t in tabs of w
        set i to i + 1
        if URL of t contains want then
          set prev to active tab index of w
          set active tab index of w to i
          set index of w to 1
          return (id of w as text) & " " & prev & " " & (title of t)
        end if
      end repeat
    end repeat
  end tell
  return ""
end run
EOF
)
[[ -z $info ]] && { echo "No Chrome tab with a URL containing '$want'."; exit 1; }
awid=${info%% *}; rest=${info#* }; prev=${rest%% *}; title=${rest#* }
sleep 1

restore() {
  osascript -e "tell application \"Google Chrome\" to set active tab index of (window id $awid) to $prev" >/dev/null 2>&1 || true
}
trap restore EXIT

# Find the window by its title, capture it, then crop with CoreGraphics.
swift - "$title" "$out" "$toolbar" "${4:-}" "${5:-}" "${6:-}" "${7:-}" <<'EOF'
import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

let a = CommandLine.arguments
let title = a[1], out = a[2], toolbar = Double(a[3]) ?? 87
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
guard let win = list.first(where: { ($0[kCGWindowOwnerName as String] as? String) == "Google Chrome"
    && ($0[kCGWindowLayer as String] as? Int) == 0
    && (($0[kCGWindowName as String] as? String) ?? "").hasPrefix(title) }),
  let id = win[kCGWindowNumber as String] as? Int,
  let bounds = win[kCGWindowBounds as String] as? [String: Double] else {
  print("No on-screen Chrome window showing '\(title)'. If window titles read blank, Screen Recording permission is missing.")
  exit(1)
}

let tmp = out + ".raw.png"
let p = Process()
p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
p.arguments = ["-x", "-o", "-l", String(id), tmp]
try p.run(); p.waitUntilExit()
guard p.terminationStatus == 0,
  let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: tmp) as CFURL, nil),
  let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { print("Capture failed."); exit(1) }

let scale = Double(img.width) / (bounds["Width"] ?? Double(img.width))

// Chrome shows a dark "... started debugging this browser" banner at the top of the active tab while a
// browser tool or extension is attached. Skip its rows, read down the left edge below the toolbar.
var top = Int(toolbar * scale)
let w0 = img.width, h0 = img.height
var px = [UInt8](repeating: 0, count: w0 * h0 * 4)
if let ctx = CGContext(data: &px, width: w0, height: h0, bitsPerComponent: 8, bytesPerRow: w0 * 4,
    space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) {
  ctx.draw(img, in: CGRect(x: 0, y: 0, width: w0, height: h0))
  func lum(_ y: Int) -> Int { let i = (y * w0 + 20) * 4; return (Int(px[i]) + Int(px[i + 1]) + Int(px[i + 2])) / 3 }
  var y = top
  while y < h0 / 3 && lum(y) < 120 { y += 1 }
  if y > top { top = y + Int(12 * scale) }  // past the banner and its shadow
}

var rect = CGRect(x: 0, y: Double(top), width: Double(img.width), height: Double(img.height - top))
if a.count > 7, let x = Double(a[4]), let y = Double(a[5]), let w = Double(a[6]), let h = Double(a[7]) {
  rect = CGRect(x: x * scale, y: Double(top) + y * scale, width: w * scale, height: h * scale)
}
guard let cropped = img.cropping(to: rect.integral),
  let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: out) as CFURL, UTType.png.identifier as CFString, 1, nil) else {
  print("Crop failed."); exit(1)
}
CGImageDestinationAddImage(dest, cropped, nil)
CGImageDestinationFinalize(dest)
try? FileManager.default.removeItem(atPath: tmp)
print("\(out): \(cropped.width) x \(cropped.height)")
EOF
