import AppKit
import WebKit
import CryptoKit

// Actual macOS WKWebView snapshots, in an isolated nonpersistent data store.
// No HTML rewriting: static mode disables page JS; dynamic mode seeds only
// Math.random through a WKUserScript so that the original demo is reproducible.
final class Capture: NSObject, WKNavigationDelegate, NSWindowDelegate {
    let output: URL
    let label: String
    let width: Int
    let height: Int
    let scale: Int
    let dynamic: Bool
    let live: Bool
    let sourceHash: String
    let sourceURL: URL
    let web: WKWebView
    let window: NSWindow
    var observations: [[String: Any]] = []
    var finished = false

    init(_ args: [String]) throws {
        guard args.count == 8, let w = Int(args[3]), let h = Int(args[4]), let s = Int(args[5]),
              (64...1600).contains(w), (64...1200).contains(h), (1...2).contains(s),
              ["static", "dynamic", "live"].contains(args[7]) else {
            throw NSError(domain: "usage: webview INPUT OUTPUT_DIR WIDTH HEIGHT SCALE LABEL static|dynamic|live", code: 1)
        }
        width = w; height = h; scale = s; label = args[6]
        live = args[7] == "live"; dynamic = args[7] != "static"
        sourceURL = URL(fileURLWithPath: args[1]).standardizedFileURL
        let source = try Data(contentsOf: sourceURL)
        sourceHash = SHA256.hash(data: source).map { String(format: "%02x", $0) }.joined()
        guard let html = String(data: source, encoding: .utf8) else { throw NSError(domain: "HTML must be UTF-8", code: 1) }
        output = URL(fileURLWithPath: args[2], isDirectory: true)
        try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        config.defaultWebpagePreferences.allowsContentJavaScript = dynamic
        if dynamic && !live {
            config.userContentController.addUserScript(WKUserScript(source: "(() => { let s=0x12345678; Math.random=()=>{s=(Math.imul(1664525,s)+1013904223)>>>0; return s/4294967296;}; })();", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        }
        web = WKWebView(frame: NSRect(x: 0,y: 0,width: w,height: h), configuration: config)
        web.appearance = NSAppearance(named: .aqua)
        window = NSWindow(contentRect: NSRect(x: 30,y: 30,width: live ? w*2+48 : w,height: live ? h+160 : h), styleMask: live ? [.titled,.closable,.miniaturizable] : .borderless, backing: .buffered, defer: false)
        super.init()
        window.isReleasedWhenClosed = false
        if live {
            window.title = "\(sourceURL.lastPathComponent) — 原始 HTML 双引擎对照"
            window.delegate = self
            let content = NSView(frame: NSRect(x:0,y:0,width:w*2+48,height:h+160))
            window.contentView = content
            let bitmap = NSImageView(frame: NSRect(x:16,y:76,width:w,height:h))
            guard let rendered = NSImage(contentsOf:output.appendingPathComponent("blitz-\(label).png")) else { throw NSError(domain:"Render the matching Blitz viewport first",code:1) }
            bitmap.image=rendered; bitmap.imageScaling = .scaleAxesIndependently
            content.addSubview(bitmap)
            web.frame = NSRect(x:w+32,y:76,width:w,height:h)
            content.addSubview(web)
            func text(_ value: String, _ x: Int, _ y: Int, _ textWidth: Int, _ height: Int, _ size: CGFloat) {
                let field=NSTextField(wrappingLabelWithString:value)
                field.frame=NSRect(x:x,y:y,width:textWidth,height:height)
                field.font = .systemFont(ofSize:size)
                field.isSelectable=true
                content.addSubview(field)
            }
            text("源文件：\(sourceURL.path)",16,h+124,w*2+16,24,13)
            text("Blitz · 原始 HTML 的静态渲染（无 JS 执行器）",16,h+86,w,28,16)
            text("WKWebView · 原始 HTML 正常运行（JS 开启）",w+32,h+86,w,28,16)
            text("两边视口均为 \(w) × \(h) CSS px。点击右侧彩色背景可换色；左侧保留 HTML 的初始 #000000 状态。",16,38,w*2+16,28,13)
            text("同一份 \(source.count) 字节原文件 · SHA-256: \(sourceHash)",16,8,w*2+16,26,11)
            NSApp.setActivationPolicy(.regular)
            window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps:true)
        } else {
            window.contentView = web
            window.alphaValue = 0
            window.orderFront(nil)
        }
        web.navigationDelegate = self
        if live {
            web.loadFileURL(sourceURL, allowingReadAccessTo: sourceURL)
        } else {
            web.loadHTMLString(html, baseURL: URL(string: "https://comparison.invalid/"))
        }
    }

    func windowWillClose(_ notification: Notification) { NSApp.terminate(nil) }

    func fail(_ error: Error) {
        guard !finished else { return }
        finished = true
        fputs("WKWebView capture failed: \(error)\n", stderr)
        exit(1)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { fail(error) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { fail(error) }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { observe("initial") }

    func observe(_ phase: String) {
        let body = """
        await document.fonts.ready;
        const el=document.getElementById('color'), cs=getComputedStyle(el), rect=el.getBoundingClientRect();
        return {phase:'\(phase)',text:el.textContent,title:document.title,
          background:getComputedStyle(document.body).backgroundColor,color:cs.color,
          fontFamily:cs.fontFamily,fontSize:cs.fontSize,fontWeight:cs.fontWeight,lineHeight:cs.lineHeight,
          cardRect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},
          viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},
          readyState:document.readyState,fontsStatus:document.fonts.status};
        """
        web.callAsyncJavaScript(body, arguments: [:], in: nil, in: .page) { result in
            switch result {
            case .failure(let error): self.fail(error)
            case .success(let value):
                guard let observation = value as? [String:Any] else { self.fail(NSError(domain:"Invalid DOM result",code:1)); return }
                self.observations.append(observation)
                DispatchQueue.main.asyncAfter(deadline: .now()+0.5) { self.snapshot(phase) }
            }
        }
    }

    func snapshot(_ phase: String) {
        let config = WKSnapshotConfiguration()
        config.rect = web.bounds
        config.snapshotWidth = NSNumber(value: width)
        config.afterScreenUpdates = true
        web.takeSnapshot(with: config) { image, error in
            if let error = error { self.fail(error); return }
            do {
                guard let tiff = image?.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff),
                      let png = bitmap.representation(using: .png, properties: [:]) else { throw NSError(domain:"Missing snapshot",code:1) }
                guard bitmap.pixelsWide == self.width*self.scale && bitmap.pixelsHigh == self.height*self.scale else {
                    throw NSError(domain:"Unexpected snapshot pixels \(bitmap.pixelsWide)x\(bitmap.pixelsHigh)",code:1)
                }
                let suffix = self.live ? "live-\(phase)" : (self.dynamic ? "dynamic-\(phase)" : "static")
                try png.write(to:self.output.appendingPathComponent("webview-\(self.label)-\(suffix).png"))
                if self.dynamic && !self.live && phase == "initial" {
                    self.web.evaluateJavaScript("document.getElementById('color').click()") { _, error in
                        if let error=error { self.fail(error) } else { self.observe("card-click") }
                    }
                } else if self.dynamic && !self.live && phase == "card-click" {
                    self.web.evaluateJavaScript("document.body.click()") { _, error in
                        if let error=error { self.fail(error) } else { self.observe("body-click") }
                    }
                } else {
                    let report: [String:Any] = ["engine":"macOS WKWebView / WebKit","mode":self.live ? "original-page-live-unseeded" : (self.dynamic ? "dynamic-seeded" : "page-javascript-disabled"), "html_rewritten":false,"source_path":self.sourceURL.path,"source_sha256":self.sourceHash,"seed":self.dynamic && !self.live ? "0x12345678 LCG" : "none", "width_css":self.width,"height_css":self.height,"scale":self.scale,"macos":ProcessInfo.processInfo.operatingSystemVersionString,"observations":self.observations]
                    let data=try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys])
                    try data.write(to:self.output.appendingPathComponent("webview-\(self.label)-\(self.live ? "live" : (self.dynamic ? "dynamic" : "static")).json"))
                    print(String(decoding:data,as:UTF8.self));fflush(stdout)
                    self.finished=true
                    if self.live {
                        print("LIVE_COMPARISON_READY pid=\(ProcessInfo.processInfo.processIdentifier)");fflush(stdout)
                    } else {
                        self.window.orderOut(nil); NSApp.terminate(nil)
                    }
                }
            } catch { self.fail(error) }
        }
    }
}

let app=NSApplication.shared
app.setActivationPolicy(.accessory)
do {
    let capture=try Capture(CommandLine.arguments)
    let timeout=Timer.scheduledTimer(withTimeInterval:45,repeats:false) { _ in capture.fail(NSError(domain:"Capture timed out",code:1)) }
    withExtendedLifetime((capture,timeout)) { app.run() }
} catch { fputs("\(error)\n",stderr); exit(1) }
