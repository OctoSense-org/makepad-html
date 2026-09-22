import AppKit
import WebKit

final class Exporter: NSObject, WKNavigationDelegate {
    let web: WKWebView
    let root: URL
    let output: URL
    init(root: URL, output: URL) {
        self.root=root; self.output=output
        let config=WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        web=WKWebView(frame:NSRect(x:0,y:0,width:600,height:700),configuration:config)
        super.init(); web.navigationDelegate=self
        web.loadFileURL(root.appendingPathComponent("editor.html"),allowingReadAccessTo:root)
    }
    func webView(_ webView:WKWebView,didFinish navigation:WKNavigation!) {
        do {
            let code=try String(contentsOf:root.appendingPathComponent("export.js"),encoding:.utf8)
            let markdown=try String(contentsOf:root.appendingPathComponent("article.md"),encoding:.utf8)
            web.callAsyncJavaScript(code,arguments:["markdown":markdown],in:nil,in:.page) { result in
                do {
                    let value=try result.get()
                    let data=try JSONSerialization.data(withJSONObject:value,options:[.prettyPrinted,.sortedKeys])
                    try data.write(to:self.output)
                    print("EXPORT_READY \(self.output.path)");fflush(stdout);NSApp.terminate(nil)
                } catch { self.fail(error) }
            }
        } catch { fail(error) }
    }
    func fail(_ error:Error) { fputs("Export failed: \(error)\n",stderr);exit(1) }
    func webView(_ webView:WKWebView,didFailProvisionalNavigation navigation:WKNavigation!,withError error:Error) {fail(error)}
}
let app=NSApplication.shared;app.setActivationPolicy(.accessory)
guard CommandLine.arguments.count==3 else {exit(1)}
let exporter=Exporter(root:URL(fileURLWithPath:CommandLine.arguments[1]),output:URL(fileURLWithPath:CommandLine.arguments[2]))
let timer=Timer.scheduledTimer(withTimeInterval:90,repeats:false){_ in exporter.fail(NSError(domain:"Export timed out",code:1))}
withExtendedLifetime((exporter,timer)){app.run()}
