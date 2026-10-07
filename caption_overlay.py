"""Transparent, draggable and resizable local captions."""
import AppKit as A, Foundation as F, json, urllib.request, base64, time, sys
TOKEN=sys.argv[1]
ready=False
class CaptionPanel(A.NSPanel):
 def canBecomeKeyWindow(self): return True
 def canBecomeMainWindow(self): return False
class Content(A.NSView):
 def resizeSubviewsWithOldSize_(self,old):
  if ready: layout()
class DragBar(A.NSTextField):
 def mouseDown_(self,event): self.window().performWindowDragWithEvent_(event)
 def mouseUp_(self,event): self.window().saveFrameUsingName_('CityWalkCaptionFrame')
class Grip(A.NSTextField):
 def mouseDown_(self,event):
  self.start=A.NSEvent.mouseLocation(); self.original=self.window().frame()
 def mouseDragged_(self,event):
  p=A.NSEvent.mouseLocation(); f=self.original
  width=max(360,min(900,f.size.width+p.x-self.start.x));height=max(300,min(760,f.size.height+self.start.y-p.y))
  self.window().setFrame_display_(A.NSMakeRect(f.origin.x,f.origin.y+f.size.height-height,width,height),True)
  layout()
 def mouseUp_(self,event): self.window().saveFrameUsingName_('CityWalkCaptionFrame')
def label(size,cls=A.NSTextField):
 v=cls.alloc().initWithFrame_(A.NSMakeRect(0,0,10,10));v.setEditable_(False);v.setSelectable_(False);v.setBezeled_(False);v.setDrawsBackground_(True);v.setBackgroundColor_(A.NSColor.colorWithCalibratedWhite_alpha_(0,.70));v.setFont_(A.NSFont.systemFontOfSize_(size));v.setTextColor_(A.NSColor.whiteColor());view.addSubview_(v);return v
def layout():
 f=view.bounds();width=f.size.width;height=f.size.height;inner=width-20
 title.setFrame_(A.NSMakeRect(10,height-30,inner,26))
 bodyheight=min(124,max(88,height*.25))
 footer.setFrame_(A.NSMakeRect(10,7,inner-32,25));grip.setFrame_(A.NSMakeRect(width-33,5,26,26))
 body.setFrame_(A.NSMakeRect(10,37,inner,bodyheight))
 image.setFrame_(A.NSMakeRect(10,43+bodyheight,inner,max(10,height-bodyheight-81)))
 body.setFont_(A.NSFont.systemFontOfSize_(max(16,min(22,width/26))))
class Poller(F.NSObject):
 def tick_(self,timer):
  try:
   req=urllib.request.Request('http://127.0.0.1:8765/caption',headers={'x-control-token':TOKEN})
   with urllib.request.urlopen(req,timeout=1) as r:d=json.load(r)
   c=d.get('caption');pending=d.get('pending')
   image.setHidden_(not bool(c));body.setHidden_(not bool(c))
   if c:
    title.setStringValue_(f"☰ 拖动 · 画面 #{c['id']} · {c['time']} · {max(0,int(time.time()-c['captured_at']))}秒前")
    body.setStringValue_(c['text'] or '暂无新信息')
    if getattr(self,'shown',None)!=c['id']:
     raw=base64.b64decode(c['thumbnail']);data=F.NSData.dataWithBytes_length_(raw,len(raw));image.setImage_(A.NSImage.alloc().initWithData_(data));self.shown=c['id']
    footer.setStringValue_(('正在解说下一帧' if pending else '文字对应上方截图')+' · 右下角拖动缩放')
   else:
    title.setStringValue_('☰ 拖动 · 正在等待 GPT' if pending else '☰ 拖动 · 陪看已就绪')
    footer.setStringValue_('右下角拖动缩放')
   if d.get('error'):footer.setStringValue_('已暂停：'+d['error'][:45])
  except Exception:footer.setStringValue_('正在连接本机陪看程序…')
app=A.NSApplication.sharedApplication();app.setActivationPolicy_(A.NSApplicationActivationPolicyAccessory)
s=A.NSScreen.screens()[0].frame()
w=CaptionPanel.alloc().initWithContentRect_styleMask_backing_defer_(A.NSMakeRect(s.size.width-538,90,520,440),A.NSWindowStyleMaskBorderless|A.NSWindowStyleMaskNonactivatingPanel,A.NSBackingStoreBuffered,False)
w.setTitle_('CityWalk · 画面解说');w.setLevel_(A.NSFloatingWindowLevel);w.setFloatingPanel_(True);w.setHidesOnDeactivate_(False);w.setCollectionBehavior_(A.NSWindowCollectionBehaviorCanJoinAllSpaces|A.NSWindowCollectionBehaviorFullScreenAuxiliary);w.setBackgroundColor_(A.NSColor.clearColor());w.setHasShadow_(False);w.setOpaque_(False)
view=Content.alloc().initWithFrame_(A.NSMakeRect(0,0,520,440));w.setContentView_(view)
title=label(12,DragBar);image=A.NSImageView.alloc().initWithFrame_(A.NSMakeRect(0,0,10,10));image.setImageScaling_(A.NSImageScaleProportionallyUpOrDown);view.addSubview_(image)
body=label(20);body.setMaximumNumberOfLines_(6);body.cell().setWraps_(True)
footer=label(10);grip=label(21,Grip);grip.setStringValue_('◢');grip.setToolTip_('拖动调整大小')
ready=True;w.setFrameAutosaveName_('CityWalkCaptionFrame');layout();w.orderFrontRegardless()
poller=Poller.alloc().init();timer=F.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(1,poller,'tick:',None,True);poller.tick_(timer);app.run()
