"""Local video preparation; AI interaction is exclusively through visible GPT web UI."""
import asyncio,base64,io,json,re,subprocess,time,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
class Prepared:
 def __init__(self,root):
  self.root=root;self.base=root/'prepared';self.base.mkdir(exist_ok=True);self.video_id='';self.duration=0;self.title='';self.url='';self.dir=self.base
  legacy=self.base/'timeline.json'
  if legacy.exists():
   try:
    data=json.loads(legacy.read_text());self.video_id=data['video_id'];self.duration=data['duration'];self.url=data.get('url','');self.title=data.get('title','')
   except (ValueError,KeyError):pass
  active=self.base/'active.json'
  if active.exists():
   try:
    data=json.loads(active.read_text());self.video_id=data['video_id'];self.duration=data['duration'];self.title=data.get('title','');self.url=data['url'];self.dir=self.cache_dir(self.video_id)
   except (ValueError,KeyError):pass
  self.dir.mkdir(exist_ok=True)
  self.progress={'status':'未准备','done':0,'total':0,'error':''};self.entries=[];self.task=None;self.process=None;self.text_complete=False
  self.video=self.dir/'video.mp4';self.audio=self.dir/'background.m4a'
  self.manifest=self.dir/'timeline.json'
  if self.manifest.exists():
   try:data=json.loads(self.manifest.read_text());self.entries=data['entries'];self.text_complete=data.get('text_complete',bool(self.entries));done=sum(bool(e.get('audio')) and (self.dir/e['audio']).exists() for e in self.entries);self.progress.update(status='已准备' if done==len(self.entries) else '文字已准备，语音待完成',done=done,total=len(self.entries))
   except (ValueError,KeyError):pass
 def save(self):self.manifest.write_text(json.dumps({'video_id':self.video_id,'duration':self.duration,'url':self.url,'title':self.title,'sampling_seconds':30,'text_complete':self.text_complete,'entries':self.entries},ensure_ascii=False,indent=2))
 def cache_dir(self,identifier):
  legacy=self.base/'timeline.json'
  if legacy.exists():
   try:
    if json.loads(legacy.read_text()).get('video_id')==identifier:return self.base
   except (ValueError,KeyError):pass
  return self.base/identifier
 async def select(self,video_url):
  match=re.fullmatch(r'https://(?:www\.)?bilibili\.com/video/(BV[A-Za-z0-9]+)(?:/)?(?:\?[^\s]*)?',video_url)
  if not match:raise RuntimeError('请使用完整的 B 站 BV 视频地址')
  identifier=match[1]
  if identifier==self.video_id and self.video.exists() and self.audio.exists():return
  self.progress.update(status='读取新视频信息',done=0,total=0,error='')
  self.process=process=await asyncio.create_subprocess_exec(sys.executable,'-m','yt_dlp','--skip-download','--dump-single-json',video_url,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
  out,err=await process.communicate()
  if process.returncode:raise RuntimeError('公开视频信息读取失败；不绕过登录、付费或安全验证')
  meta=json.loads(out);duration=float(meta.get('duration',0))
  if duration<=0 or duration>14400:raise RuntimeError('目前支持四小时以内的公开单条视频')
  self.video_id=identifier;self.duration=duration;self.title=str(meta.get('title',''));self.url=video_url;self.dir=self.cache_dir(identifier);self.dir.mkdir(exist_ok=True)
  self.video=self.dir/'video.mp4';self.audio=self.dir/'background.m4a';self.manifest=self.dir/'timeline.json';self.entries=[];self.text_complete=False
  (self.base/'active.json').write_text(json.dumps({'video_id':identifier,'duration':duration,'title':self.title,'url':video_url},ensure_ascii=False))
  if self.manifest.exists():
   data=json.loads(self.manifest.read_text());self.entries=data['entries'];self.text_complete=data.get('text_complete',bool(self.entries))
  for label,fmt,path in [('下载视频','bestvideo[height<=1080][vcodec^=avc1]/bestvideo[height<=1080][ext=mp4]',self.video),('下载原声','bestaudio[ext=m4a]/bestaudio',self.audio)]:
   if path.exists():continue
   self.progress['status']=label
   self.process=process=await asyncio.create_subprocess_exec(sys.executable,'-m','yt_dlp','--no-progress','-f',fmt,'-o',str(path),video_url,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
   _,err=await process.communicate()
   if process.returncode:raise RuntimeError('公开媒体下载失败；未读取浏览器 cookie 或绕过访问限制')
 async def run(self,browser,url,video_url=None):
  try:
   if video_url:await self.select(video_url)
   if self.entries and all(e.get('audio') and (self.dir/e['audio']).exists() for e in self.entries):
    self.progress.update(status='已准备',done=len(self.entries),total=len(self.entries));return
   if not browser.process or browser.process.poll() is not None:await browser.open(url);await asyncio.sleep(3)
   if not self.text_complete:
    self.progress.update(status='准备视频画面',error='',done=0,total=11)
    frames=self.dir/'frames';frames.mkdir(exist_ok=True)
    if not list(frames.glob('*.jpg')):
     import imageio_ffmpeg
     self.process=p=await asyncio.create_subprocess_exec(imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-i',str(self.video),'-vf','fps=1/30,scale=640:-1','-q:v','3',str(frames/'%04d.jpg'))
     if await p.wait():raise RuntimeError('视频预览提取失败')
    files=sorted(frames.glob('[0-9]*.jpg'))
    batches=list(range(0,len(files),12));self.progress['total']=len(batches)
    entries=[]
    for batch,i in enumerate(batches):
     canvas=Image.new('RGB',(1920,1560),'#111111');draw=ImageDraw.Draw(canvas)
     font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
     times=[]
     for j,f in enumerate(files[i:i+12]):
      t=(i+j)*30+15;times.append(t);x=(j%3)*640;y=(j//3)*390
      canvas.paste(Image.open(f),(x,y+30));draw.text((x+8,y+6),f'{t//60:02}:{t%60:02} | t={t}s',fill='white',font=font)
     out=io.BytesIO();canvas.save(out,format='PNG')
     self.progress['status']=f'GPT 准备第 {batch+1}/{len(batches)} 段'
     prompt='这些是同一个街景视频的连续画面，每张顶部标明真实视频秒数。请逐张看，选最多3张值得讲解的清晰路牌、店名或地标，避免相邻重复，禁止凭地名猜具体门牌。每条讲解不超过70个汉字，自然口语，不提问，不含VOICE字段。只输出JSON数组，每项为{"at":画面顶部的秒数,"text":"讲解正文"}。没有信息输出[]。合法秒数：'+str(times)
     text=await browser.analyze(out.getvalue(),url,prompt=prompt,raw=True)
     match=re.search(r'\[.*\]',text,re.S)
     if not match:raise RuntimeError('GPT 未返回可校验的时间轴，已保存之前的准备结果')
     data=json.loads(match[0])
     for item in data:
      at=float(item['at']);body=str(item['text']).strip()
      if at not in times or not body or len(body)>160 or 'VOICE' in body:continue
      f=files[int((at-15)/30)];thumb=base64.b64encode(f.read_bytes()).decode()
      entries.append({'id':len(entries)+1,'at':at,'end':at+25,'text':body,'thumbnail':thumb,'audio':None})
     self.entries=entries;self.save();self.progress['done']=batch+1
    self.text_complete=True;self.save()
   entries=self.entries
   self.progress.update(status='准备 GPT 自然语音',done=0,total=len(entries))
   for i,item in enumerate(entries):
    if item.get('audio') and (self.dir/item['audio']).exists():continue
    await browser.text_task('只原样输出下面这段讲解正文，禁止任何前缀、序号、引号、VOICE字段或解释：\n'+item['text'])
    target=self.dir/f"voice-{item['id']:03}.mp3"
    await browser.read_aloud(target)
    if not target.exists():raise RuntimeError('网页朗读未提供可保存的音频，字幕已准备，语音缓存尚未完成')
    item['audio']=target.name;self.save();self.progress['done']=i+1
   self.progress['status']='已准备'
  except asyncio.CancelledError:
   if self.process and self.process.returncode is None:self.process.terminate();await self.process.wait()
   self.progress['status']='已停止，缓存保留';raise
  except Exception as e:self.progress.update(status='准备未完成',error=str(e) if isinstance(e,RuntimeError) else type(e).__name__)
