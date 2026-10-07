import asyncio, contextlib, json, os, secrets, socket, subprocess, sys, time
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, Response, FileResponse
import uvicorn, qrcode, io, logging, base64
from logging.handlers import RotatingFileHandler
from capture import capture, bounds, difference, png, video_target
from chatgpt_browser import Browser
from prepared import Prepared
ROOT=Path(__file__).resolve().parent
log=logging.getLogger('citywalk'); log.setLevel(logging.INFO)
handler=RotatingFileHandler(ROOT/'events.log',maxBytes=100000,backupCount=1); handler.setFormatter(logging.Formatter('%(asctime)s %(message)s')); log.addHandler(handler)
DEFAULT={'interval':5,'url':'','cooldown':20,'threshold':.38,'quiet':True,'auto':True,'voice':True,'level':2,'rate':180}
config=DEFAULT.copy()
try: config.update(json.loads((ROOT/'config.json').read_text()))
except (FileNotFoundError,ValueError): pass
# Region must be explicitly selected each session.
state={'running':False,'stop_id':0,'busy':False,'region':'video','screen':bounds(),'error':'','last_send':None,'last_capture':None,'last_voice':'','difference':0,'queued':False,'hotkey':'未启用（可使用控制页立即分析）'}
prepared=Prepared(ROOT)
browser=Browser(ROOT); queue=asyncio.Queue(maxsize=1); last_image=None; last_time=0; token=secrets.token_urlsafe(24)
server=None; tasks=[]; caffeinate=None; speech=None; picker=None; overlay=None; caption=None; pending=None; frame_id=0

def lan_ip():
 for interface in ['en0','en1']:
  try:
   address=subprocess.check_output(['/usr/sbin/ipconfig','getifaddr',interface],stderr=subprocess.DEVNULL,text=True).strip()
   if address and not address.startswith('198.18.'): return address
  except subprocess.CalledProcessError: pass
 s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
 try: s.connect(('192.0.2.1',80)); return s.getsockname()[0]
 except OSError: return '127.0.0.1'
 finally: s.close()
IP=lan_ip()
@contextlib.asynccontextmanager
async def lifespan(app):
 global caffeinate,tasks,overlay
 log.info('启动')
 caffeinate=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())])
 tasks=[asyncio.create_task(observe()),asyncio.create_task(worker()),asyncio.create_task(hotkey())]
 state['running']=False
 yield
 state['running']=False
 log.info('关闭')
 if prepared.task and not prepared.task.done():prepared.task.cancel();await asyncio.gather(prepared.task,return_exceptions=True)
 for t in tasks: t.cancel()
 await asyncio.gather(*tasks,return_exceptions=True)
 if picker and picker.returncode is None: picker.terminate()
 if speech and speech.returncode is None: speech.terminate()
 with contextlib.suppress(Exception): await browser.close()
 if overlay and overlay.poll() is None: overlay.terminate()
 for row in subprocess.check_output(['ps','-axo','pid=,comm='],text=True).splitlines():
  pair=row.strip().split(None,1)
  if len(pair)==2 and pair[1]==str(ROOT/'CityWalk Captions.app/Contents/MacOS/CityWalkCaptions'):
   with contextlib.suppress(ProcessLookupError):os.kill(int(pair[0]),15)
 if caffeinate: caffeinate.terminate(); caffeinate.wait(timeout=3)
 with contextlib.suppress(FileNotFoundError): (ROOT/'control-url.txt').unlink()
app=FastAPI(lifespan=lifespan)
@app.middleware('http')
async def auth(request,call_next):
 path=request.url.path
 if (path=='/voice-prep' or path.startswith('/record/')) and (not request.client or request.client.host not in ['127.0.0.1','::1']):return Response('仅允许本机访问',status_code=403)
 supplied=request.headers.get('x-control-token','')
 if path in ['/','/qr','/player','/voice-prep'] or path.startswith('/media/'):supplied=request.query_params.get('token','')
 if not supplied or not secrets.compare_digest(supplied,token):return Response('控制口令无效',status_code=403)
 response=await call_next(request);response.headers['Cache-Control']='no-store';return response
@app.get('/')
async def index(): return HTMLResponse((ROOT/'control.html').read_text().replace('__TOKEN__',token).replace('__LAN__',f'http://{IP}:8765/?token={token}'))
@app.get('/voice-prep')
async def voice_prep_ui():return HTMLResponse((ROOT/'voice-prep.html').read_text().replace('__TOKEN__',token))
@app.get('/player')
async def player():return HTMLResponse((ROOT/'player.html').read_text().replace('__TOKEN__',token))
@app.get('/media/{name}')
async def media(name:str,v:str|None=None):
 folder=prepared.dir
 if v:
  if not __import__('re').fullmatch(r'BV[A-Za-z0-9]{5,32}',v):raise HTTPException(400,'视频编号无效')
  folder=prepared.cache_dir(v)
 if name=='video':path=folder/'video.mp4'
 elif name=='background':path=folder/'background.m4a'
 elif __import__('re').fullmatch(r'voice-\d{3}\.mp3',name):path=folder/name
 else:raise HTTPException(404)
 if not path.exists():raise HTTPException(404,'视频尚未准备')
 return FileResponse(path)
@app.get('/diagnostic')
@app.post('/diagnostic')
async def diagnostic():
 frames=[]
 if prepared.task:
  obj=prepared.task.get_coro()
  while obj and len(frames)<12:
   frames.append(getattr(obj,'__qualname__',type(obj).__name__));obj=getattr(obj,'cr_await',getattr(obj,'gi_yieldfrom',None))
 return {'phase':browser.status,'task':frames,'browser_pid':browser.process.pid if browser.process else None,'page':browser.page.url.split('?')[0] if browser.page else None}
@app.post('/prepare-voices')
async def prepare_voices():
 if prepared.task and not prepared.task.done():raise HTTPException(409,'正在准备')
 state['running']=False
 async def run():
  try:
   for i,item in enumerate(prepared.entries):
    if item.get('audio') and (prepared.dir/item['audio']).exists():continue
    prepared.progress.update(status=f'GPT 网页生成语音 {i+1}/{len(prepared.entries)}',done=i,total=len(prepared.entries),error='')
    browser.status='连接专用 GPT 网页';await browser.connect()
    browser.status='发送纯正文朗读准备';await browser.text_task('只原样输出这一句正文，不附加解释、编号或字段：'+item['text'])
    target=prepared.dir/f"voice-{item['id']:03}.mp3"
    browser.status='缓存 GPT 网页朗读';await browser.read_aloud(target)
    if not target.exists():raise RuntimeError('GPT 自然语音未保存，未用机械语音替代')
    item['audio']=target.name;prepared.save();prepared.progress['done']=i+1
   prepared.progress['status']='已准备'
  except Exception as e:prepared.progress.update(status='语音准备未完成',error=str(e) if isinstance(e,RuntimeError) else type(e).__name__)
 prepared.task=asyncio.create_task(run());return {'ok':True}
recording=None
@app.post('/prepared/import')
async def import_prepared(req:Request):
 if prepared.task and not prepared.task.done():prepared.task.cancel();await asyncio.gather(prepared.task,return_exceptions=True)
 data=await req.json();entries=[]
 for item in sorted(data.get('entries',[]),key=lambda x:x['at']):
  at=float(item['at']);body=str(item['text']).strip()
  if not 0<=at<prepared.duration or not body or len(body)>160 or 'VOICE' in body:raise HTTPException(400,'讲解格式无效')
  f=prepared.dir/'frames'/f'{int((at-15)/30)+1:04}.jpg'
  if not f.exists():raise HTTPException(400,'讲解时间缺少对应视频画面')
  entries.append({'id':len(entries)+1,'at':at,'end':at+25,'text':body,'thumbnail':base64.b64encode(f.read_bytes()).decode(),'audio':None})
 prepared.entries=entries;prepared.save();prepared.progress.update(status='文字已准备，语音准备中',done=0,total=len(entries),error='')
 return {'ok':True,'count':len(entries)}
@app.post('/record/start')
async def record_start(req:Request):
 global recording
 if recording:raise HTTPException(409,'正在录制网页朗读')
 d=await req.json();identifier=int(d['id']);pid=int(d['pid'])
 if not any(e['id']==identifier for e in prepared.entries):raise HTTPException(400,'讲解编号无效')
 rows=subprocess.check_output(['ps','-axo','pid=,comm='],text=True).splitlines()
 if not any(row.strip().split(None,1)==[str(pid),'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'] for row in rows):raise HTTPException(400,'只允许录制 Chrome 网页声音')
 path=prepared.dir/f'capture-{identifier:03}-{int(time.time())}.m4a'
 process=await asyncio.create_subprocess_exec(str(ROOT/'RecordWebVoice'),str(pid),str(path),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
 try:
  ready=await asyncio.wait_for(process.stdout.readline(),15)
  if b'READY' not in ready:raise RuntimeError('网页声音录制未启动；请检查已授权的终端录屏权限')
 except Exception:
  if process.returncode is None:process.terminate()
  raise HTTPException(503,'网页声音录制未启动')
 recording=(process,path,identifier);return {'ok':True}
@app.post('/record/stop')
async def record_stop():
 global recording
 if not recording:raise HTTPException(400,'没有录制任务')
 process,path,identifier=recording;recording=None
 process.stdin.write(b'\n');await process.stdin.drain();await asyncio.wait_for(process.wait(),20)
 if process.returncode or not path.exists():raise HTTPException(503,'网页音频未保存')
 import imageio_ffmpeg
 target=prepared.dir/f'voice-{identifier:03}.mp3'
 p=await asyncio.create_subprocess_exec(imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(path),'-af','silenceremove=start_periods=1:start_duration=0.1:start_threshold=-45dB,loudnorm=I=-16:TP=-1.5:LRA=11',str(target))
 if await p.wait():raise HTTPException(503,'网页音频转换失败')
 item=next(e for e in prepared.entries if e['id']==identifier);item['audio']=target.name;prepared.save()
 done=sum(bool(e.get('audio')) for e in prepared.entries);prepared.progress.update(status='已准备' if done==len(prepared.entries) else '文字已准备，语音准备中',done=done,total=len(prepared.entries))
 return {'ok':True,'id':identifier,'bytes':target.stat().st_size}
@app.get('/prepared')
async def prepared_status():return {'stop_id':state['stop_id'],'video_id':prepared.video_id,'media_ready':prepared.video.exists() and prepared.audio.exists(),'video_url':prepared.url,'duration':prepared.duration,'progress':prepared.progress,'entries':prepared.entries,'preparing':bool(prepared.task and not prepared.task.done())}
@app.post('/prepare')
async def prepare_video(req:Request):
 if state['busy']:raise HTTPException(409,'当前网页正在生成，请等这次完成')
 if prepared.task and not prepared.task.done():return {'ok':True}
 state['running']=False
 data=await req.json() if await req.body() else {}
 prepared.task=asyncio.create_task(prepared.run(browser,config['url'],data.get('video_url') or None))
 return {'ok':True}
@app.get('/qr')
async def qr():
 f=io.BytesIO(); qrcode.make(f'http://{IP}:8765/?token={token}').save(f,format='PNG'); return Response(f.getvalue(),media_type='image/png')
@app.get('/status')
async def status():
 import Quartz as Q
 return {**state,'screen_permission':bool(Q.CGPreflightScreenCaptureAccess()),'browser':browser.status,'config':config,'lan':f'http://{IP}:8765/?token={token}'}
@app.get('/video-info')
async def video_info():
 import Quartz as Q
 rows=Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionAll,Q.kCGNullWindowID)
 pids={r.get('kCGWindowOwnerPID') for r in rows if r.get('kCGWindowOwnerName')=='Google Chrome' and 'bilibili' in (r.get('kCGWindowName','') or '').lower()}
 return [{'id':r['kCGWindowNumber'],'name':r.get('kCGWindowName',''),'bounds':dict(r['kCGWindowBounds']),'onscreen':bool(r.get('kCGWindowIsOnscreen'))} for r in rows if r.get('kCGWindowOwnerPID') in pids]
@app.get('/capture-preview')
async def capture_preview():
 if not state['region']:raise HTTPException(400,'未设置视频区域')
 return Response(png(capture(state['region'],state['screen'])),media_type='image/png')
@app.get('/caption')
async def current_caption(): return {'caption':caption,'pending':pending,'error':state['error'],'running':state['running']}
@app.post('/settings')
async def settings(req:Request):
 d=await req.json()
 url=d.get('url','').strip()
 import re
 if url and not re.fullmatch(r'https://chatgpt\.com/c/[A-Za-z0-9-]+',url): raise HTTPException(400,'请粘贴 https://chatgpt.com/c/... 固定对话网址')
 try:
  c={'interval':max(5,min(300,float(d.get('interval',config.get('interval',5)))))}
  c.update({k:bool(d[k]) for k in ['quiet','auto','voice']}); c.update(url=url,cooldown=max(20,float(d['cooldown'])),threshold=min(.95,max(.05,float(d['threshold']))),level=max(1,min(3,int(d['level']))),rate=max(100,min(300,int(d['rate']))))
 except (ValueError,KeyError): raise HTTPException(400,'配置数值无效')
 config.update(c); (ROOT/'config.json').write_text(json.dumps(config,ensure_ascii=False)); return {'ok':True}
@app.post('/region')
async def region(req:Request):
 global last_image
 if state['busy']: raise HTTPException(409,'请等待当前分析完成')
 d=await req.json()
 try:
  rect=[int(v) for v in d['region']]; screen=bounds()
  x,y,w,h=rect; sx,sy,sw,sh=screen
  if w<30 or h<30 or x<sx or y<sy or x+w>sx+sw or y+h>sy+sh: raise ValueError()
 except (KeyError,ValueError,TypeError): raise HTTPException(400,'视频范围无效')
 state.update(running=False,region=rect,screen=screen,error=''); last_image=None
 return {'ok':True,'region':rect}
@app.post('/select')
async def select():
 global picker,last_image
 if state['busy']: raise HTTPException(409,'请等待当前分析完成再框选')
 state['running']=False
 if picker and picker.returncode is None: raise HTTPException(409,'正在框选，Esc 取消')
 picker=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'select_region.py'),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
 try: out,err=await asyncio.wait_for(picker.communicate(),120)
 except asyncio.TimeoutError:
  picker.terminate(); await picker.wait(); raise HTTPException(408,'框选超时，请重试')
 if picker.returncode and not out:
  state['error']='区域选择工具未能启动，请重启陪看程序'
  log.error('区域选择失败: %s',err.decode(errors='replace')[-1500:])
  raise HTTPException(500,state['error'])
 if not out:
  raise HTTPException(400,'已取消选择，请重新框选视频')
 if out:
  d=json.loads(out); state.update(region=d['region'],screen=d['screen'],error=''); last_image=None
 return {'ok':True}
@app.post('/action/{action}')
async def action(action:str):
 global recording,caption,pending
 if action=='permission':
  import Quartz as Q
  granted=bool(Q.CGPreflightScreenCaptureAccess()) or bool(Q.CGRequestScreenCaptureAccess())
  state['error']='' if granted else '请在系统提示中允许录屏；在系统设置开启提示所列应用后，退出并重新双击启动器'
  return {'ok':granted}
 if action=='exit':
  state['running']=False; server.should_exit=True
 elif action in ['pause','stop']:
  state['running']=False;state['stop_id']+=1;caption=None;pending=None
  if recording:
   process=recording['proc']
   if process.returncode is None:process.terminate();await process.wait()
   recording=None
  if speech and speech.returncode is None:speech.terminate()
  if overlay and overlay.poll() is None:overlay.terminate()
  if prepared.process and prepared.process.returncode is None:prepared.process.terminate()
  cancelled=[]
  if prepared.task and not prepared.task.done():prepared.task.cancel();cancelled.append(prepared.task)
  if len(tasks)>1:tasks[1].cancel();cancelled.append(tasks[1])
  if browser.process and browser.process.poll() is None:browser.process.terminate()
  await asyncio.gather(*cancelled,return_exceptions=True)
  prepared.progress['status']='已停止，缓存保留'
  while not queue.empty():queue.get_nowait();queue.task_done()
  await browser.close()
  state.update(busy=False,queued=False,error='')
  if len(tasks)>1:tasks[1]=asyncio.create_task(worker())
 elif action=='browser':
  if state['busy'] or (prepared.task and not prepared.task.done()): raise HTTPException(409,'请先停止当前任务')
  try: await browser.open(config['url'] or 'https://chatgpt.com'); state['error']=''
  except Exception: raise HTTPException(503,'浏览器打开失败，请检查网络或重启程序')
 elif action=='auto-video':
  state.update(running=False,region='video',screen=bounds(),error='')
 elif action in ['start','resume']:
  if not state['region'] or not config['url']: raise HTTPException(400,'请先框选视频并保存对话网址')
  if not browser.process or browser.process.poll() is not None:await browser.open(config['url'])
  state.update(running=True,error='')
 elif action=='force':
  if not state['region'] or not config['url']: raise HTTPException(400,'请先框选视频并保存对话网址')
  if queue.empty(): queue.put_nowait(True); state['queued']=True
 return {'ok':True}
async def observe():
 global last_image
 while True:
  await asyncio.sleep(config.get('interval',5))
  if prepared.entries or (prepared.task and not prepared.task.done()) or not state['running'] or state['busy'] or not queue.empty() or not config['auto']: continue
  try:
   im=capture(state['region'],state['screen']); state['last_capture']=time.strftime('%H:%M:%S');state['error']=''
   score=1 if last_image is None else difference(im,last_image); state['difference']=round(score,3); log.info('场景变化 %.3f',score)
   threshold=config['threshold'] if config['quiet'] else config['threshold']*.7
   if score>=threshold and time.monotonic()-last_time>=config['cooldown']: queue.put_nowait(False); state['queued']=True
  except Exception as e:
   state['error']=str(e)
   if not any(k in str(e) for k in ['黑屏','未找到显示B站']):state['running']=False
async def worker():
 global last_image,last_time,speech,caption,pending,frame_id
 while True:
  forced=await queue.get(); state.update(busy=True,queued=False)
  try:
   # Force bypasses scene threshold but cooldown still limits actual sends.
   await asyncio.sleep(max(0,config['cooldown']-(time.monotonic()-last_time)))
   if not forced and (not state['running'] or not config['auto']): continue
   while browser.page and not browser.page.is_closed() and await browser.generating(): await asyncio.sleep(3)
   im=capture(state['region'],state['screen']); state['last_capture']=time.strftime('%H:%M:%S')
   last_time=time.monotonic(); state['last_send']=time.strftime('%H:%M:%S'); last_image=im.copy()
   log.info('截图成功，进入发送任务')
   frame_id+=1
   pending={'id':frame_id,'time':state['last_capture'],'captured_at':time.time()}
   source=pending.copy(); thumb=im.copy(); thumb.thumbnail((1184,666)); out=io.BytesIO(); thumb.save(out,format='JPEG',quality=90)
   source['thumbnail']=base64.b64encode(out.getvalue()).decode()
   priority,voice,text=await browser.analyze(png(im),config['url'],f"画面 #{frame_id} · 截图 {source['time']}")
   source['text']=text; caption=source; pending=None
   log.info('ChatGPT 回复完成 VOICE_PRIORITY=%d',priority)
   state['last_voice']=voice; state['error']=''
   if config['voice'] and priority>0 and voice:
    try: await browser.read_aloud()
    except RuntimeError as e: state['error']=str(e)
  except asyncio.CancelledError: raise
  except Exception as e:
   # Do not persist raw Playwright error text (may contain chat excerpts).
   state['error']=str(e) if isinstance(e,RuntimeError) else '网页操作失败：请检查登录、附件、网络和网页状态，处理后继续'
   if not any(k in str(e) for k in ['黑屏','未找到显示B站']):state['running']=False
   log.info('分析任务失败，等待或暂停')
  finally: pending=None; state['busy']=False; queue.task_done()
async def hotkey():
 # Global polling does not capture keystrokes or install an accessibility event tap.
 import Quartz as Q
 previous=False
 while True:
  flags=Q.CGEventSourceFlagsState(Q.kCGEventSourceStateCombinedSessionState)
  pressed=bool(flags & Q.kCGEventFlagMaskControl and flags & Q.kCGEventFlagMaskAlternate and Q.CGEventSourceKeyState(Q.kCGEventSourceStateCombinedSessionState,49))
  state['hotkey']='Control + Option + Space（若系统不允许监听，可用控制页）'
  if pressed and not previous and state['running'] and state['region'] and config['url'] and queue.empty(): queue.put_nowait(True); state['queued']=True
  previous=pressed; await asyncio.sleep(.08)
if __name__=='__main__':
 import webbrowser, threading
 probe=socket.socket(); probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
 try:
  probe.bind(('0.0.0.0',8765))
 except OSError:
  print('CityWalk 已在运行，或 8765 端口被占用。请使用已打开的控制页。'); sys.exit(1)
 finally: probe.close()
 local=f'http://127.0.0.1:8765/?token={token}'
 (ROOT/'control-url.txt').write_text(local); (ROOT/'control-url.txt').chmod(0o600)
 print('\nCityWalk Companion\n本机：'+local+'\n手机：'+f'http://{IP}:8765/?token={token}',flush=True)
 browser.control_url=local
 server=uvicorn.Server(uvicorn.Config(app,host='0.0.0.0',port=8765,log_level='warning',access_log=False)); server.run()
