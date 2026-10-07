import asyncio,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepared import Prepared
class OfflineBrowser:
 process=None
 async def open(self,*args):raise AssertionError('Complete cache must not open GPT')
class CacheTests(unittest.IsolatedAsyncioTestCase):
 async def test_complete_cache_reused_without_gpt(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);folder=root/'prepared';folder.mkdir()
   (folder/'voice-001.mp3').write_bytes(b'fixture')
   (folder/'timeline.json').write_text(json.dumps({'video_id':'BV12345678','duration':60,'entries':[{'id':1,'at':15,'text':'fixture','audio':'voice-001.mp3'}]}))
   prepared=Prepared(root);await prepared.run(OfflineBrowser(),'')
   self.assertEqual(prepared.progress['status'],'已准备')
 async def test_only_public_bv_urls_accepted(self):
  with tempfile.TemporaryDirectory() as directory:
   prepared=Prepared(Path(directory))
   with self.assertRaisesRegex(RuntimeError,'BV'):
    await prepared.select('https://example.com/video/private')
if __name__=='__main__':unittest.main()
