import Quartz as Q
from PIL import Image
import imagehash, io

def bounds():
 r=Q.CGDisplayBounds(Q.CGMainDisplayID()); return [int(r.origin.x),int(r.origin.y),int(r.size.width),int(r.size.height)]
def video_target():
 rows=Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionOnScreenOnly,Q.kCGNullWindowID)
 for win in rows:
  if win.get('kCGWindowOwnerName')=='Google Chrome' and 'bilibili' in (win.get('kCGWindowName','') or '').lower():
   b=win['kCGWindowBounds'];sx,sy,sw,sh=bounds();x,y,w,h=[int(b[k]) for k in ['X','Y','Width','Height']]
   if w>=sw-4 and h>=sh-4: return [x+2,y+48,w-4,h-96]
   if abs(w-1081)<=4 and abs(h-683)<=4:return [x+19,y+257,662,370]
   raise RuntimeError('视频窗口尺寸已改变，请恢复全屏；移动窗口无需重选')
 raise RuntimeError('未找到显示B站视频的Chrome窗口，请切回视频')
def capture(region,screen):
 if not Q.CGPreflightScreenCaptureAccess():
  Q.CGRequestScreenCaptureAccess(); raise RuntimeError('请为启动程序的终端开启屏幕与系统音频录制权限，再退出重启')
 if bounds()!=screen: raise RuntimeError('屏幕尺寸发生变化，请重新选择视频区域')
 if region=='video':region=video_target()
 x,y,w,h=region; sx,sy,sw,sh=screen
 if w<30 or h<30 or x<sx or y<sy or x+w>sx+sw or y+h>sy+sh: raise RuntimeError('视频区域无效，请重新框选')
 # Capture only the identified Bilibili window inside the selected video rect.
 target=None
 allwins=Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionAll,Q.kCGNullWindowID)
 video_pids={w.get('kCGWindowOwnerPID') for w in allwins if w.get('kCGWindowOwnerName')=='Google Chrome' and 'bilibili' in (w.get('kCGWindowName','') or '').lower()}
 for win in Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionOnScreenOnly,Q.kCGNullWindowID):
  name=win.get('kCGWindowName','') or ''
  if win.get('kCGWindowOwnerName')!='Google Chrome' or ('bilibili' not in name.lower() and win.get('kCGWindowOwnerPID') not in video_pids): continue
  b=win.get('kCGWindowBounds',{}); bx=b.get('X',0); by=b.get('Y',0); bw=b.get('Width',0); bh=b.get('Height',0)
  if bx<=x and by<=y and bx+bw>=x+w and by+bh>=y+h: target=win['kCGWindowNumber']; break
 if target is None: raise RuntimeError('视频窗口已移动或关闭，请重新设置视频区域')
 cg=Q.CGWindowListCreateImage(Q.CGRectMake(x,y,w,h),Q.kCGWindowListOptionIncludingWindow,target,Q.kCGWindowImageBoundsIgnoreFraming)
 if cg is None: raise RuntimeError('区域截图失败，请检查录屏权限')
 width=Q.CGImageGetWidth(cg); height=Q.CGImageGetHeight(cg); stride=Q.CGImageGetBytesPerRow(cg)
 raw=Q.CGDataProviderCopyData(Q.CGImageGetDataProvider(cg))
 im=Image.frombuffer('RGBA',(width,height),bytes(raw),'raw','BGRA',stride,1).convert('RGB')
 if sum(im.resize((64,36)).convert('L').getdata())/(64*36)<10: raise RuntimeError('视频暂时黑屏或缓冲，画面恢复后自动继续')
 return im

def difference(a,b): return (imagehash.phash(a)-imagehash.phash(b))/64

def png(im):
 f=io.BytesIO(); im.save(f,format='PNG'); return f.getvalue()
