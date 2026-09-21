import AppKit
import WebKit
import CryptoKit

final class FlippedDocument: NSView { override var isFlipped: Bool { true } }

// Exact-source comparison: the page comes from a loopback snapshot server.
// Page scripts are disabled. App-owned DOM measurements don't edit the source.
final class HTMLComparison: NSObject, WKNavigationDelegate, NSWindowDelegate {
    let output: URL
    let source: URL
    let pageURL: URL
    let width: Int
    let height: Int
    let scale: Int
    let label: String
    let captureOnly: Bool
    let web: WKWebView
    let window: NSWindow
    var report: [String: Any]
    var tiles: [[String: Any]] = []
    var positions: [Int] = []
    var started = false
    var finished = false

    init(_ args: [String]) throws {
        guard (8...9).contains(args.count), let w = Int(args[3]), let h = Int(args[4]), let s = Int(args[5]),
              (320...1000).contains(w), (320...1000).contains(h), (1...2).contains(s),
              let url = URL(string: args[7]), url.host == "127.0.0.1" else {
            throw NSError(domain: "usage: html5_webview INPUT OUTPUT WIDTH HEIGHT SCALE LABEL LOOPBACK_URL", code: 1)
        }
        width=w; height=h; scale=s; label=args[6]; pageURL=url
        captureOnly=args.count == 9 && args[8] == "capture"
        source=URL(fileURLWithPath:args[1]).standardizedFileURL
        output=URL(fileURLWithPath:args[2],isDirectory:true)
        let bytes=try Data(contentsOf:source)
        let hash=SHA256.hash(data:bytes).map { String(format:"%02x",$0) }.joined()
        report=["engine":"macOS WKWebView / WebKit", "html_rewritten":false,
                "source_path":source.path,"source_sha256":hash,"source_bytes":bytes.count,
                "page_scripts_enabled":false,"width_css":w,"height_css":h,"scale":s,
                "macos":ProcessInfo.processInfo.operatingSystemVersionString]
        let config=WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        config.defaultWebpagePreferences.allowsContentJavaScript=false
        web=WKWebView(frame:NSRect(x:w+32,y:64,width:w,height:h),configuration:config)
        web.appearance=NSAppearance(named:.aqua)
        window=NSWindow(contentRect:NSRect(x:30,y:30,width:w*2+48,height:h+156),
                        styleMask:[.titled,.closable,.miniaturizable],backing:.buffered,defer:false)
        super.init()
        window.isReleasedWhenClosed=false; window.delegate=self
        window.title="HTML5 Example Page — 你贴出的 HTML · Blitz / WKWebView"
        let content=NSView(frame:NSRect(x:0,y:0,width:w*2+48,height:h+156))
        window.contentView=content
        let scroll=NSScrollView(frame:NSRect(x:16,y:64,width:w,height:h))
        scroll.hasVerticalScroller=true; scroll.scrollerStyle = .overlay
        scroll.backgroundColor = .white
        let infoPath=output.appendingPathComponent("blitz-\(label).json")
        let info: [String:Any]
        if captureOnly && !FileManager.default.fileExists(atPath:infoPath.path) {
            info=["full_height_px":h*s]
        } else {
            info=try JSONSerialization.jsonObject(with:Data(contentsOf:infoPath)) as! [String:Any]
        }
        let fullHeight=(info["full_height_px"] as! NSNumber).intValue/s
        let document=FlippedDocument(frame:NSRect(x:0,y:0,width:w,height:fullHeight))
        let picture=NSImageView(frame:document.bounds)
        let rendered=NSImage(contentsOf:output.appendingPathComponent("blitz-\(label)-full.png"))
        guard let image=rendered ?? (captureOnly ? NSImage(size:NSSize(width:w,height:h)) : nil) else {
            throw NSError(domain:"Missing matching Blitz full-page render",code:1)
        }
        picture.image=image; picture.imageScaling = .scaleAxesIndependently
        document.addSubview(picture); scroll.documentView=document
        scroll.contentView.scroll(to:.zero)
        content.addSubview(scroll); content.addSubview(web)
        func text(_ value:String,_ x:Int,_ y:Int,_ tw:Int,_ th:Int,_ size:CGFloat) {
            let field=NSTextField(wrappingLabelWithString:value)
            field.frame=NSRect(x:x,y:y,width:tw,height:th)
            field.font = .systemFont(ofSize:size); field.isSelectable=true; content.addSubview(field)
        }
        text("HTML5 Example Page · 本次粘贴的完整 HTML · 两侧可独立滚动",16,h+117,w*2+16,28,17)
        let gifEnabled=(info["image_decode_probes"] as? [[String:Any]])?.contains { ($0["format"] as? String)=="Gif" && ($0["decoded"] as? Bool)==true } ?? false
        text(gifEnabled ? "Blitz · GIF / WOFF 已启用 · 原生静态渲染" : "Blitz · 当前集成的原生引擎静态渲染",16,h+76,w,28,15)
        text("WKWebView · macOS WebKit 原生控件可交互",w+32,h+76,w,28,15)
        text("同源 CSS/字体快照 · 三个外部图片地址返回 404 · 两侧页面脚本关闭",16,32,w*2+16,24,12)
        text("\(w) × \(h) CSS px / \(s)× · 原文 SHA-256: \(hash)",16,4,w*2+16,23,11)
        web.navigationDelegate=self
        if captureOnly {
            window.alphaValue=0; window.orderFront(nil)
        } else {
            NSApp.setActivationPolicy(.regular)
            window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps:true)
        }
        web.load(URLRequest(url:pageURL))
    }

    func windowWillClose(_ notification:Notification) { NSApp.terminate(nil) }
    func fail(_ error:Error) {
        guard !finished else { return }
        fputs("HTML5 comparison failed: \(error)\n",stderr); exit(1)
    }
    func webView(_ webView:WKWebView,didFail navigation:WKNavigation!,withError error:Error) { fail(error) }
    func webView(_ webView:WKWebView,didFailProvisionalNavigation navigation:WKNavigation!,withError error:Error) { fail(error) }
    func webView(_ webView:WKWebView,decidePolicyFor action:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void) {
        let u=action.request.url
        decisionHandler(u?.host == pageURL.host && u?.port == pageURL.port && u?.path == pageURL.path && action.navigationType != .formSubmitted ? .allow : .cancel)
    }
    func webView(_ webView:WKWebView,didFinish navigation:WKNavigation!) {
        guard !started else { return }; started=true
        let code="""
        await document.fonts.ready;
        const selectors=['[data-probe]','h1','nav','article','article > p','article > ul','article > ol','aside','img','button','blockquote','details','pre','section','table','form','input','textarea','body > footer'];
        const elements=Object.fromEntries(selectors.map(s=>[s,[...document.querySelectorAll(s)].map(el=>{
          const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height};
        })]));
        return {title:document.title,content_height_css:document.documentElement.scrollHeight,elements,
          viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},
          body_font:getComputedStyle(document.body).font,
          fonts:[...document.fonts].map(f=>({family:f.family,status:f.status})),
          images:[...document.images].map(i=>({src:i.getAttribute('src'),complete:i.complete,naturalWidth:i.naturalWidth,naturalHeight:i.naturalHeight})),
          details:[...document.querySelectorAll('details')].map(d=>({open:d.open,hidden_content_height:d.querySelector('p').getBoundingClientRect().height}))};
        """
        web.callAsyncJavaScript(code,arguments:[:],in:nil,in:.page) { result in
            switch result {
            case .failure(let error):self.fail(error)
            case .success(let value):
                guard let data=value as? [String:Any],let full=(data["content_height_css"] as? NSNumber)?.intValue,
                      full<=8192 else { self.fail(NSError(domain:"Invalid page geometry",code:1));return }
                self.report["observation"]=data
                self.positions=Array(stride(from:0,through:max(0,full-self.height),by:self.height))
                if self.positions.last != max(0,full-self.height) { self.positions.append(max(0,full-self.height)) }
                self.captureNext()
            }
        }
    }
    func captureNext() {
        guard !positions.isEmpty else { finish();return }
        let y=positions.removeFirst()
        web.evaluateJavaScript("window.scrollTo(0,\(y)); window.scrollY") { value,error in
            if let error=error { self.fail(error);return }
            let actual=(value as? NSNumber)?.intValue ?? -1
            guard actual==y else { self.fail(NSError(domain:"Unexpected scroll offset \(actual), expected \(y)",code:1));return }
            DispatchQueue.main.asyncAfter(deadline:.now()+0.35) {
                let config=WKSnapshotConfiguration()
                config.rect=self.web.bounds; config.snapshotWidth=NSNumber(value:self.width); config.afterScreenUpdates=true
                self.web.takeSnapshot(with:config) { image,error in
                    if let error=error { self.fail(error);return }
                    do {
                        guard let tiff=image?.tiffRepresentation,let bitmap=NSBitmapImageRep(data:tiff),
                              let png=bitmap.representation(using:.png,properties:[:]),
                              bitmap.pixelsWide==self.width*self.scale,bitmap.pixelsHigh==self.height*self.scale else {
                            throw NSError(domain:"Invalid WKWebView capture dimensions",code:1)
                        }
                        let name="webview-\(self.label)-tile-\(y).png"
                        try png.write(to:self.output.appendingPathComponent(name))
                        self.tiles.append(["y_css":y,"file":name])
                        self.captureNext()
                    } catch { self.fail(error) }
                }
            }
        }
    }
    func finish() {
        report["tiles"]=tiles
        do {
            let data=try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys])
            try data.write(to:output.appendingPathComponent("webview-\(label).json"))
            web.evaluateJavaScript("window.scrollTo(0,0)") { _,error in
                if let error=error { self.fail(error);return }
                self.finished=true
                print("HTML5_COMPARISON_READY pid=\(ProcessInfo.processInfo.processIdentifier) report=\(self.output.path)/webview-\(self.label).json");fflush(stdout)
                if self.captureOnly { NSApp.terminate(nil) }
            }
        } catch { fail(error) }
    }
}

let app=NSApplication.shared
app.setActivationPolicy(.accessory)
do {
    let comparison=try HTMLComparison(CommandLine.arguments)
    let timeout=Timer.scheduledTimer(withTimeInterval:60,repeats:false) { _ in comparison.fail(NSError(domain:"Capture timed out",code:1)) }
    withExtendedLifetime((comparison,timeout)) { app.run() }
} catch { fputs("\(error)\n",stderr);exit(1) }
