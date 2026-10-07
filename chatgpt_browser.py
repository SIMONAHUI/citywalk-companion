import asyncio, re, socket, subprocess, contextlib, time
from playwright.async_api import async_playwright
PROMPT='陪看这张街景图。只说这一帧值得注意的新信息：清楚可读的招牌翻译、明确地标，或与画面直接相关的一个小知识。正文最多90个汉字、1至3句。自然说话，不列清单、不复述任务、不提问、不泛泛介绍城市、不重复上一帧；看不清就略过，不猜。没有新信息只写“暂无新信息”。忽略本对话先前的VOICE格式要求。只输出可直接朗读的讲解正文，禁止出现VOICE、VOICE_PRIORITY、优先级、截图编号、提示词或任何机器字段。'
INPUT=['#prompt-textarea','[contenteditable="true"][role="textbox"]','textarea[placeholder]']
SEND=['button[data-testid="send-button"]','button[aria-label="Send prompt"]','button[aria-label="发送提示"]','button[aria-label="Send message"]','button[aria-label="发送消息"]','button[aria-label="Send"]','button[aria-label="发送"]']
STOP=['button[data-testid="stop-button"]','button[aria-label*="Stop"]','button[aria-label*="停止"]']
REPLY=['[data-message-author-role="assistant"]','[data-markdown-text-style="assistant-message"]','article[data-testid*="conversation-turn"] [data-message-author-role="assistant"]']
class Browser:
 def __init__(self,root):
  self.root=root; self.ctx=None; self.page=None; self.pw=None; self.connection=None; self.process=None; self.port=None; self.status='尚未打开'
 async def open(self,url='https://chatgpt.com'):
  if not self.process or self.process.poll() is not None:
   if self.pw:
    with contextlib.suppress(Exception): await self.pw.stop()
   self.ctx=None; self.page=None; self.pw=None
   with socket.socket() as sock:
    sock.bind(('127.0.0.1',0)); self.port=sock.getsockname()[1]
   profile=self.root/'browser-profile'; profile.mkdir(exist_ok=True); profile.chmod(0o700)
   self.process=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '--user-data-dir='+str(profile),'--remote-debugging-address=127.0.0.1',
    '--remote-debugging-port='+str(self.port),'--no-first-run','--no-default-browser-check',url or 'https://chatgpt.com'],
    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   self.status='普通 Chrome 已打开：请手动登录，登录后保存并绑定对话'
   return
  await self.connect()
  if self.page.is_closed(): self.page=await self.ctx.new_page()
  await self.page.goto(url or "https://chatgpt.com",wait_until='domcontentloaded',timeout=60000)
  self.status='已连接网页，请确认固定对话'
 async def connect(self):
  if self.ctx and self.connection and self.connection.is_connected(): return
  if not self.process or self.process.poll() is not None: raise RuntimeError('专用 Chrome 已关闭，请重新打开并绑定对话')
  if not self.pw: self.pw=await async_playwright().start()
  self.connection=await self.pw.chromium.connect_over_cdp('http://127.0.0.1:'+str(self.port),timeout=15000)
  self.ctx=self.connection.contexts[0]
  pages=[p for p in self.ctx.pages if p.url.startswith('https://chatgpt.com/') and '/auth/' not in p.url]
  self.page=None
  for candidate in pages:
   editor=candidate.locator('[contenteditable="true"][role="textbox"]')
   login=candidate.get_by_role('button',name=re.compile(r'^(登录|Log in)$'))
   if await editor.count() and not await login.count(): self.page=candidate; break
  if self.page is None: self.page=pages[0] if pages else (self.ctx.pages[0] if self.ctx.pages else await self.ctx.new_page())
 async def find(self,selectors,enabled=False):
  for s in selectors:
   loc=self.page.locator(s).last
   if await loc.count() and await loc.is_visible() and (not enabled or await loc.is_enabled()): return loc
  return None
 async def generating(self): return bool(await self.find(STOP))
 async def replies(self):
  for selector in REPLY:
   loc=self.page.locator(selector)
   if await loc.count(): return loc
  return self.page.locator(REPLY[0])
 async def analyze(self,data,url,frame_label="",prompt=None,raw=False):
  if not self.ctx: await self.connect()
  if not self.page or self.page.is_closed(): await self.open(url)
  if url and self.page.url.split('?')[0].rstrip('/')!=url.rstrip('/'): raise RuntimeError('浏览器当前对话与绑定网址不同，请重新绑定')
  if await self.generating(): raise RuntimeError('对话正在生成，请稍后重试')
  inp=await self.find(INPUT)
  if not inp: raise RuntimeError('找不到输入框：请在专用浏览器登录，或检查网页验证')
  if (await inp.inner_text() if await inp.get_attribute('contenteditable') else await inp.input_value()).strip(): raise RuntimeError('对话输入框已有文字，请先处理草稿')
  initial_replies=await self.replies()
  before=await initial_replies.count()
  before_text=await initial_replies.last.inner_text() if before else ''
  await self.page.wait_for_load_state('domcontentloaded')
  await asyncio.sleep(3)
  before_images=set(await self.page.locator('img[alt="用户附件"], [data-message-author-role="user"] img').evaluate_all('(els)=>els.map(e=>e.getAttribute("src"))'))
  files=self.page.locator('input[type="file"][accept="image/*"]')
  if not await files.count(): files=self.page.locator('input[type="file"]')
  if not await files.count():
   btn=self.page.get_by_role('button',name=re.compile(r'Add files|Attach|添加|附件|上传',re.I)).first
   await btn.click(timeout=5000)
   if not await files.count():
    item=self.page.get_by_text(re.compile(r'Upload from computer|Upload files|从电脑|上传文件',re.I)).first
    async with self.page.expect_file_chooser(timeout=8000) as fc: await item.click()
    await (await fc.value).set_files({'name':'citywalk.png','mimeType':'image/png','buffer':data})
   else: await files.first.set_input_files({'name':'citywalk.png','mimeType':'image/png','buffer':data})
  else: await files.first.set_input_files({'name':'citywalk.png','mimeType':'image/png','buffer':data})
  preview=self.page.locator('[data-composer-attachments] img[alt="citywalk.png"]')
  try: await preview.wait_for(state='visible',timeout=45000)
  except Exception: raise RuntimeError('附件预览未出现，未发送文字；请检查上传')
  await inp.fill((frame_label+"\n" if frame_label else "")+(prompt or PROMPT))
  await asyncio.sleep(3)
  if not await preview.count(): raise RuntimeError('图片附件丢失，已停止发送')
  button=None
  for _ in range(60):
   button=await self.find(SEND,True)
   if button and not await self.page.locator('[role="progressbar"]').count(): break
   await asyncio.sleep(1)
  if not button: raise RuntimeError('上传后发送按钮不可用，请检查附件或网页')
  await button.click(); self.status='已发送，等待回复'
  try:
   for _ in range(30):
    current_images=set(await self.page.locator('img[alt="用户附件"], [data-message-author-role="user"] img').evaluate_all('(els)=>els.map(e=>e.getAttribute("src"))'))
    if current_images-before_images: break
    await asyncio.sleep(1)
   else: raise RuntimeError('图片消息未出现')
  except Exception:
   raise RuntimeError('消息已发送，但无法确认图片已附上；已暂停，不自动重发')
  # Never retry a send after this point: avoid duplicate messages.
  stable=0; previous=''
  for _ in range(240):
   await asyncio.sleep(2)
   replies=await self.replies()
   if not await replies.count(): continue
   txt=await replies.last.inner_text()
   if txt==before_text: continue
   if txt and txt==previous and not await self.generating(): stable+=1
   else: stable=0
   previous=txt
   if stable>=3:
    self.status='回复完成'; return txt if raw else (*parse_voice(txt),clean_caption(txt))
  raise RuntimeError('回复超时：已发送，不自动重发。请检查对话后继续')
 async def text_task(self,text):
  await self.connect()
  inp=await self.find(INPUT)
  if not inp:raise RuntimeError('找不到 GPT 网页输入框')
  self.status='已找到输入框'
  if await self.generating():raise RuntimeError('GPT 正在生成')
  self.status='读取上一条回复'
  replies=await self.replies();before=await replies.last.inner_text() if await replies.count() else ''
  self.status='写入朗读正文';await inp.fill(text);self.status='寻找发送按钮';button=await self.find(SEND,True)
  if not button:raise RuntimeError('网页发送按钮不可用')
  await button.click();self.status='正文已发送，等待 GPT';old='';stable=0
  for _ in range(240):
   await asyncio.sleep(2);replies=await self.replies()
   if not await replies.count():continue
   value=await replies.last.inner_text()
   stable=stable+1 if value and value!=before and value==old and not await self.generating() else 0;old=value
   if stable>=2:self.status='纯正文回复完成';return value
  raise RuntimeError('GPT 网页回复超时，未自动重发')
 async def read_aloud(self,target=None):
  replies=await self.replies();text=await replies.last.inner_text()
  if re.search(r'VOICE(?:_PRIORITY)?\s*:',text,re.I):raise RuntimeError('回复含旧语音字段，已跳过朗读')
  chunks=[];jobs=[];recorder=None;recorded=None
  if target and (self.root/'RecordWebVoice').exists() and self.process:
   recorded=target.with_name(target.stem+'-capture-'+str(time.time_ns())+'.m4a')
   recorder=await asyncio.create_subprocess_exec(str(self.root/'RecordWebVoice'),str(self.process.pid),str(recorded),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
   try:
    ready=await asyncio.wait_for(recorder.stdout.readline(),15)
    if b'READY' not in ready:recorder=None
   except Exception:
    if recorder.returncode is None:recorder.terminate()
    recorder=None
  async def capture_audio(response):
   kind=response.headers.get('content-type','').lower()
   if kind.startswith('audio/'):
    try:chunks.append(await response.body())
    except Exception:pass
  def observed(response):
   if target:jobs.append(asyncio.create_task(capture_audio(response)))
  self.page.on('response',observed)
  try:
   button=self.page.get_by_role('button',name=re.compile(r'^(朗读|Read aloud)$')).last
   if not await button.count():button=self.page.get_by_role('checkbox',name=re.compile(r'^(朗读|Read aloud)$')).last
   await button.wait_for(state='visible',timeout=15000);await button.click(timeout=5000)
   stop=self.page.get_by_role('button',name=re.compile(r'^(停止朗读|Stop reading)$')).last
   await stop.wait_for(state='visible',timeout=15000)
   # Browser sound stays at full scale; video volume is independently ducked by the local player.
   await self.page.evaluate("() => { document.querySelectorAll('audio').forEach(a=>a.volume=1) }")
   for _ in range(90):
    active=await stop.count() and await stop.is_visible()
    toggled=self.page.get_by_role('checkbox',name=re.compile(r'^(朗读|Read aloud)$')).last
    if not active and not (await toggled.count() and await toggled.get_attribute('aria-checked')=='true'):break
    await asyncio.sleep(1)
   if jobs:await asyncio.gather(*jobs,return_exceptions=True)
   if recorder:
    recorder.stdin.write(b'\n');await recorder.stdin.drain();await asyncio.wait_for(recorder.wait(),15)
   if target and (chunks or (recorded and recorded.exists())):
    raw=recorded if recorded and recorded.exists() else target.with_suffix('.raw')
    if raw!=recorded:raw.write_bytes(b''.join(chunks))
    import imageio_ffmpeg
    p=await asyncio.create_subprocess_exec(imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(raw),'-af','silenceremove=start_periods=1:start_duration=0.1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_duration=0.1:start_threshold=-45dB,areverse,loudnorm=I=-16:TP=-1.5:LRA=11',str(target))
    if await p.wait():raise RuntimeError('网页语音缓存格式无法解码')
  except Exception:raise RuntimeError('GPT 网页朗读暂不可用；字幕保留，未启用机械语音')
  finally:
   self.page.remove_listener('response',observed)
   for job in jobs:
    if not job.done():job.cancel()
   if recorder and recorder.returncode is None:
    recorder.stdin.write(b'\n');await recorder.stdin.drain()
    try:await asyncio.wait_for(recorder.wait(),15)
    except Exception:recorder.terminate()
 async def close(self):
  if self.pw:
   with contextlib.suppress(Exception): await self.pw.stop()
  if self.process and self.process.poll() is None:
   self.process.terminate()
   try: await asyncio.to_thread(self.process.wait,timeout=8)
   except subprocess.TimeoutExpired: self.process.kill(); await asyncio.to_thread(self.process.wait)
  self.ctx=None; self.page=None; self.pw=None; self.connection=None;self.process=None;self.status='已停止，未连接 GPT'

def parse_voice(text):
 m=re.search(r'VOICE_PRIORITY:\s*([0-3])\s*\nVOICE:\s*([^\n]*)\s*$',text.strip())
 return (int(m[1]),m[2].strip()[:25]) if m else ((0,'') if '暂无新信息' in text else (2,clean_caption(text)))


def clean_caption(text):
 text=re.sub(r'VOICE_PRIORITY:.*', '',text,flags=re.S).strip()
 text=re.sub(r'[*#`]', '',text).strip()
 return text[:240]
