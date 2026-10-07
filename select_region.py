import AppKit as A, Quartz as Q, json, sys
class SelectionWindow(A.NSWindow):
 def canBecomeKeyWindow(self): return True
 def canBecomeMainWindow(self): return True
class Selector(A.NSView):
 def acceptsFirstResponder(self): return True
 def mouseDown_(self,e): self.start=e.locationInWindow(); self.end=self.start; self.setNeedsDisplay_(True)
 def mouseDragged_(self,e): self.end=e.locationInWindow(); self.setNeedsDisplay_(True)
 def mouseUp_(self,e):
  self.end=e.locationInWindow(); x=min(self.start.x,self.end.x); y=min(self.start.y,self.end.y); w=abs(self.start.x-self.end.x); h=abs(self.start.y-self.end.y)
  if w>=30 and h>=30:
   height=self.bounds().size.height
   print(json.dumps({'region':[int(x),int(height-y-h),int(w),int(h)],'screen':[0,0,int(self.bounds().size.width),int(height)]}),flush=True)
   A.NSApplication.sharedApplication().terminate_(None)
  else: self.setNeedsDisplay_(True)
 def keyDown_(self,e):
  if e.keyCode()==53: A.NSApplication.sharedApplication().terminate_(None)
 def drawRect_(self,r):
  A.NSColor.colorWithCalibratedWhite_alpha_(0,.18).setFill(); A.NSBezierPath.fillRect_(self.bounds())
  attrs={A.NSFontAttributeName:A.NSFont.boldSystemFontOfSize_(22),A.NSForegroundColorAttributeName:A.NSColor.whiteColor(),A.NSBackgroundColorAttributeName:A.NSColor.blackColor()}
  A.NSString.stringWithString_("按住鼠标从视频左上角拖到右下角，松开确认；Esc取消").drawAtPoint_withAttributes_(A.NSMakePoint(40,self.bounds().size.height-70),attrs)
  if hasattr(self,'start'):
   A.NSColor.systemRedColor().setStroke(); p=A.NSBezierPath.bezierPathWithRect_(A.NSMakeRect(min(self.start.x,self.end.x),min(self.start.y,self.end.y),abs(self.start.x-self.end.x),abs(self.start.y-self.end.y))); p.setLineWidth_(3); p.stroke()
app=A.NSApplication.sharedApplication(); app.setActivationPolicy_(A.NSApplicationActivationPolicyRegular)
s=A.NSScreen.screens()[0]; r=s.frame()
w=SelectionWindow.alloc().initWithContentRect_styleMask_backing_defer_(r,A.NSWindowStyleMaskBorderless,A.NSBackingStoreBuffered,False)
w.setCollectionBehavior_(A.NSWindowCollectionBehaviorCanJoinAllSpaces | A.NSWindowCollectionBehaviorFullScreenAuxiliary); w.setTitle_("拖动框选视频区域，松开确认，Esc取消"); w.setOpaque_(False); w.setBackgroundColor_(A.NSColor.clearColor()); w.setLevel_(A.NSScreenSaverWindowLevel); w.setContentView_(Selector.alloc().initWithFrame_(A.NSMakeRect(0,0,r.size.width,r.size.height))); w.setIgnoresMouseEvents_(False); w.orderFrontRegardless(); w.makeKeyAndOrderFront_(None); w.makeFirstResponder_(w.contentView()); app.activateIgnoringOtherApps_(True); app.run()
