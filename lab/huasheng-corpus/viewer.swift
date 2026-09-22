import AppKit
import WebKit

final class ReportViewer:NSObject,WKNavigationDelegate,NSWindowDelegate {
    let web:WKWebView
    let window:NSWindow
    let output:URL
    init(_ root:URL) {
        output=root
        let config=WKWebViewConfiguration();config.websiteDataStore = .nonPersistent()
        web=WKWebView(frame:NSRect(x:0,y:0,width:1160,height:850),configuration:config)
        window=NSWindow(contentRect:web.frame,styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
        super.init();window.isReleasedWhenClosed=false;window.delegate=self
        window.title="花生编辑器 · 20 个主题 · Blitz / WKWebView 实测"
        window.contentView=web;web.navigationDelegate=self;web.appearance=NSAppearance(named:.aqua)
        window.center();window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
        web.loadFileURL(root.appendingPathComponent("index.html"),allowingReadAccessTo:root)
    }
    func windowWillClose(_ notification:Notification){NSApp.terminate(nil)}
    func webView(_ webView:WKWebView,didFinish navigation:WKNavigation!){
        let code="""
        const checks=[];
        for(const option of document.getElementById('case').options){
          for(const width of ['390','600']){
            document.getElementById('case').value=option.value;
            document.getElementById('width').value=width;
            for(const mode of ['pair','diff']){
              document.getElementById('mode').value=mode;update();
              const img=document.getElementById('capture');await img.decode();
              checks.push({theme:option.value,width,mode:document.getElementById('mode').value,pixels:[img.naturalWidth,img.naturalHeight]});
            }
          }
        }
        document.getElementById('case').value='wechat-default';document.getElementById('width').value='390';document.getElementById('mode').value='pair';update();
        await document.getElementById('capture').decode();
        return {theme_options:document.getElementById('case').options.length,checks};
        """
        web.callAsyncJavaScript(code,arguments:[:],in:nil,in:.page){ result in
            do {
                let value=try result.get()
                let data=try JSONSerialization.data(withJSONObject:value,options:[.prettyPrinted,.sortedKeys])
                try data.write(to:self.output.appendingPathComponent("report-validation.json"))
                print("REPORT_READY pid=\(ProcessInfo.processInfo.processIdentifier) all 40 pairs and available differences loaded");fflush(stdout)
            } catch { fputs("Report verification failed: \(error)\n",stderr) }
        }
    }
}
let app=NSApplication.shared;app.setActivationPolicy(.regular)
guard CommandLine.arguments.count==2 else {exit(1)}
let viewer=ReportViewer(URL(fileURLWithPath:CommandLine.arguments[1]))
withExtendedLifetime(viewer){app.run()}
