import AppKit
import WebKit

final class ReportViewer:NSObject,WKNavigationDelegate,NSWindowDelegate {
    let web:WKWebView
    let window:NSWindow
    init(_ path:String) {
        let config=WKWebViewConfiguration();config.websiteDataStore = .nonPersistent()
        web=WKWebView(frame:NSRect(x:0,y:0,width:1220,height:800),configuration:config)
        window=NSWindow(contentRect:web.frame,styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
        super.init()
        window.isReleasedWhenClosed=false;window.delegate=self
        window.title="公众号 HTML/CSS · Blitz / WKWebView 截图对照报告"
        window.contentView=web;web.navigationDelegate=self
        web.appearance=NSAppearance(named:.aqua)
        window.center();window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
        let url=URL(fileURLWithPath:path).standardizedFileURL
        web.loadFileURL(url,allowingReadAccessTo:url.deletingLastPathComponent())
    }
    func windowWillClose(_ notification:Notification){NSApp.terminate(nil)}
    func webView(_ webView:WKWebView,didFinish navigation:WKNavigation!){
        let code="""
        const checks=[];
        for(const [name,variant,mode] of [['13-layout','media','diff'],['02-headings-quotes','extended','pair'],['02-headings-quotes','patched','pair'],['08-carousel','patched','pair'],['10-svg-css','patched','pair']]){
          document.getElementById('case').value=name;
          document.getElementById('variant').value=variant;
          document.getElementById('mode').value=mode;update();
          const image=document.getElementById('capture');await image.decode();
          checks.push({name,variant,mode,title:document.getElementById('title').textContent,width:image.naturalWidth,height:image.naturalHeight});
        }
        return {options:document.getElementById('case').options.length,checks};
        """
        web.callAsyncJavaScript(code,arguments:[:],in:nil,in:.page){ result in
            switch result {
            case .success(let value):print("REPORT_READY pid=\(ProcessInfo.processInfo.processIdentifier) \(value ?? "")");fflush(stdout)
            case .failure(let error):fputs("Report verification failed: \(error)\n",stderr)
            }
        }
    }
}
let app=NSApplication.shared;app.setActivationPolicy(.regular)
guard CommandLine.arguments.count==2 else {exit(1)}
let viewer=ReportViewer(CommandLine.arguments[1])
withExtendedLifetime(viewer){app.run()}
