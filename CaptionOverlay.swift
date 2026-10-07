import Cocoa
import Darwin
let passedToken = CommandLine.arguments.dropFirst().first ?? ""
let controlURL = (try? String(contentsOfFile:NSHomeDirectory()+"/CityWalkCompanion/control-url.txt",encoding:.utf8))?.trimmingCharacters(in:.whitespacesAndNewlines) ?? ""
let token = passedToken.isEmpty ? (URLComponents(string:controlURL)?.queryItems?.first(where:{$0.name=="token"})?.value ?? "") : passedToken
let instanceLock=open("/private/tmp/citywalk-caption.lock",O_CREAT|O_RDWR,0o600)
if flock(instanceLock,LOCK_EX|LOCK_NB) != 0 {exit(0)}
class DragBar: NSTextField {
 override func acceptsFirstMouse(for event:NSEvent?) -> Bool {true}
 override func mouseDown(with event:NSEvent) { window?.performDrag(with:event); window?.saveFrame(usingName:"CityWalkCaption") }
}
class Grip: NSTextField {
 override var mouseDownCanMoveWindow:Bool {false}
 override func acceptsFirstMouse(for event:NSEvent?) -> Bool {true}
 override func mouseDown(with event:NSEvent) {
  guard let w=window else{return}; let start=NSEvent.mouseLocation, original=w.frame
  while let e=w.nextEvent(matching:[.leftMouseDragged,.leftMouseUp]) {
   if e.type == .leftMouseUp {break}
   let p=NSEvent.mouseLocation
   let width=max(360,min(900,original.width+p.x-start.x)), height=max(300,min(760,original.height+start.y-p.y))
   w.setFrame(NSRect(x:original.minX,y:original.maxY-height,width:width,height:height),display:true)
  }
  w.saveFrame(usingName:"CityWalkCaption")
 }
}
class Content:NSView {
 override func resizeSubviews(withOldSize old:NSSize){ hud?.layout() }
}
class HUDPanel:NSPanel {override var canBecomeKey:Bool {true}}
var hud:HUD?
class HUD:NSObject {
 let panel:NSPanel
 let content=Content()
 let smaller=NSButton(title:"−",target:nil,action:nil), larger=NSButton(title:"+",target:nil,action:nil)
 let title=DragBar(), body=NSTextField(), footer=NSTextField(), grip=Grip(), image=NSImageView()
 var timer:Timer?, shown:Int = -1, waiting=false
 override init(){
  let s=NSScreen.main!.frame
  panel=HUDPanel(contentRect:NSRect(x:s.maxX-538,y:90,width:520,height:440),styleMask:[.titled,.closable,.resizable,.fullSizeContentView,.nonactivatingPanel],backing:.buffered,defer:false)
  super.init()
  panel.title="CityWalk · 画面解说";panel.titlebarAppearsTransparent=true;panel.titleVisibility = .hidden;panel.isMovableByWindowBackground=false;panel.maxSize=NSSize(width:900,height:760);panel.minSize=NSSize(width:360,height:300); panel.level = .floating;panel.isFloatingPanel=true;panel.hidesOnDeactivate=false;panel.collectionBehavior=[.canJoinAllSpaces,.fullScreenAuxiliary];panel.backgroundColor = .clear;panel.isOpaque=false;panel.hasShadow=false
  panel.contentView=content
  for field in [title,body,footer,grip] {
   field.isEditable=false;field.isSelectable=false;field.isBezeled=false;field.drawsBackground=true;field.backgroundColor=NSColor.black.withAlphaComponent(0.7);field.textColor = .white;content.addSubview(field)
  }
  title.font = .systemFont(ofSize:12); footer.font = .systemFont(ofSize:10);grip.font = .systemFont(ofSize:21);grip.stringValue="◢";grip.toolTip="拖动缩放"
  body.cell?.wraps=true;body.maximumNumberOfLines=6;image.imageScaling = .scaleProportionallyUpOrDown;content.addSubview(image)
  smaller.target=self;smaller.action=#selector(shrink);larger.target=self;larger.action=#selector(grow)
  for button in [smaller,larger] {button.bezelStyle = .smallSquare;button.font = .systemFont(ofSize:17);content.addSubview(button)}
  panel.setFrameAutosaveName("CityWalkCaption");panel.orderFrontRegardless()
  timer=Timer.scheduledTimer(withTimeInterval:1,repeats:true){[weak self] _ in self?.tick()};tick()
 }
 @objc func shrink(){resize(by:0.85)}
 @objc func grow(){resize(by:1.15)}
 func resize(by factor:CGFloat){let f=panel.frame;let width=max(360,min(900,f.width*factor)),height=max(300,min(760,f.height*factor));panel.setFrame(NSRect(x:f.minX,y:f.maxY-height,width:width,height:height),display:true);panel.saveFrame(usingName:"CityWalkCaption")}
 func layout(){
  let width=content.bounds.width,height=content.bounds.height,inner=width-20,bh=min(124,max(88,height*0.25))
  title.frame=NSRect(x:88,y:height-30,width:inner-144,height:26);smaller.frame=NSRect(x:width-70,y:height-30,width:28,height:26);larger.frame=NSRect(x:width-38,y:height-30,width:28,height:26);footer.frame=NSRect(x:10,y:7,width:inner-32,height:25);grip.frame=NSRect(x:width-33,y:5,width:26,height:26)
  body.frame=NSRect(x:10,y:37,width:inner,height:bh);body.font = .systemFont(ofSize:max(16,min(22,width/26)))
  image.frame=NSRect(x:10,y:43+bh,width:inner,height:max(10,height-bh-81))
 }
 func tick(){
  guard !waiting else{return};waiting=true
  var req=URLRequest(url:URL(string:"http://127.0.0.1:8765/caption")!);req.setValue(token,forHTTPHeaderField:"x-control-token");req.timeoutInterval=2
  URLSession.shared.dataTask(with:req){[weak self] data,_,_ in
   DispatchQueue.main.async {
    guard let self=self else{return};self.waiting=false
    guard let data=data,let d=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] else {self.footer.stringValue="正在连接本机陪看程序…";return}
    if let c=d["caption"] as? [String:Any],let id=c["id"] as? Int {
     let stamp=c["time"] as? String ?? "", age=max(0,Int(Date().timeIntervalSince1970-(c["captured_at"] as? Double ?? Date().timeIntervalSince1970)))
     self.title.stringValue="☰ 拖动 · 画面 #\(id) · \(stamp) · \(age)秒前"
     self.body.stringValue=c["text"] as? String ?? ""
     self.image.isHidden=false;self.body.isHidden=false
     if id != self.shown,let b64=c["thumbnail"] as? String,let raw=Data(base64Encoded:b64){self.image.image=NSImage(data:raw);self.shown=id}
     self.footer.stringValue="文字对应上方截图 · 右下角拖动缩放"
    } else {self.title.stringValue="☰ 拖动 · 陪看已就绪";self.body.isHidden=true;self.image.isHidden=true;self.footer.stringValue="右下角拖动缩放"}
    if let pending=d["pending"] as? [String:Any],let id=pending["id"] as? Int {self.footer.stringValue="正在解说画面 #\(id) · 右下角拖动缩放"}
    if let err=d["error"] as? String,!err.isEmpty {self.footer.stringValue=((d["running"] as? Bool == true) ? "等待：" : "已暂停：")+String(err.prefix(45))}
   }
  }.resume()
 }
}
let app=NSApplication.shared;app.setActivationPolicy(.accessory);hud=HUD();hud!.layout();app.run()
