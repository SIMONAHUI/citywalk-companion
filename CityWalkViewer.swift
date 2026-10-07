import Cocoa
import WebKit
final class AppDelegate:NSObject,NSApplicationDelegate {
 var window:NSWindow!
 var web:WKWebView!
 var timer:Timer?
 var attempts=0
 let root:URL = {let folder=Bundle.main.bundleURL.deletingLastPathComponent();return FileManager.default.fileExists(atPath:folder.appendingPathComponent("start.command").path) ? folder : FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("CityWalkCompanion")}()
 func applicationDidFinishLaunching(_ note:Notification) {
  window=NSWindow(contentRect:NSRect(x:0,y:0,width:1180,height:760),styleMask:[.titled,.closable,.resizable,.miniaturizable],backing:.buffered,defer:false)
  window.title="CityWalk Companion";window.minSize=NSSize(width:720,height:480);window.center();window.backgroundColor = .black
  let config=WKWebViewConfiguration();config.preferences.isElementFullscreenEnabled=true
  web=WKWebView(frame:window.contentView!.bounds,configuration:config);web.autoresizingMask=[.width,.height];window.contentView=web
  window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
  probe(startIfMissing:true)
 }
 func probe(startIfMissing:Bool) {
  let path=root.appendingPathComponent("control-url.txt")
  if let value=try? String(contentsOf:path,encoding:.utf8),let url=URL(string:value.trimmingCharacters(in:.whitespacesAndNewlines)),var components=URLComponents(url:url,resolvingAgainstBaseURL:false),let token=components.queryItems?.first(where:{$0.name=="token"})?.value {
   components.path="/status";components.query=nil
   if let statusURL=components.url {
    var request=URLRequest(url:statusURL);request.timeoutInterval=2;request.setValue(token,forHTTPHeaderField:"x-control-token")
    URLSession.shared.dataTask(with:request){[weak self] _,response,_ in
     DispatchQueue.main.async {
      guard let self=self else{return}
      if (response as? HTTPURLResponse)?.statusCode==200 {
       var player=URLComponents(url:url,resolvingAgainstBaseURL:false)!;player.path="/player"
       self.web.load(URLRequest(url:player.url!));self.window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
      } else {self.launchAndRetry(startIfMissing:startIfMissing)}
     }
    }.resume();return
   }
  }
  launchAndRetry(startIfMissing:startIfMissing)
 }
 func launchAndRetry(startIfMissing:Bool) {
  if startIfMissing {
   let p=Process();p.executableURL=URL(fileURLWithPath:"/usr/bin/open");p.arguments=["-a","/System/Applications/Utilities/Terminal.app",root.appendingPathComponent("start.command").path];try? p.run()
  }
  attempts+=1
  guard attempts<30 else {web.loadHTMLString("<body style='background:#111;color:white;font:22px system-ui;padding:40px'>本地服务未启动。请双击桌面的 CityWalk Companion.command 查看提示。</body>",baseURL:nil);return}
  DispatchQueue.main.asyncAfter(deadline:.now()+1){[weak self] in self?.probe(startIfMissing:false)}
 }
 func applicationWillTerminate(_ note:Notification) {
  guard let value=try? String(contentsOf:root.appendingPathComponent("control-url.txt"),encoding:.utf8),let url=URL(string:value.trimmingCharacters(in:.whitespacesAndNewlines)),var components=URLComponents(url:url,resolvingAgainstBaseURL:false),let token=components.queryItems?.first(where:{$0.name=="token"})?.value else{return}
  components.path="/action/exit";components.query=nil
  guard let endpoint=components.url else{return}
  var request=URLRequest(url:endpoint);request.httpMethod="POST";request.timeoutInterval=1;request.setValue(token,forHTTPHeaderField:"x-control-token")
  let semaphore=DispatchSemaphore(value:0)
  URLSession.shared.dataTask(with:request){_,_,_ in semaphore.signal()}.resume();_ = semaphore.wait(timeout:.now()+1)
 }
 func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool {true}
}
let application=NSApplication.shared
let delegate=AppDelegate();application.delegate=delegate;application.setActivationPolicy(.regular);application.run()
