"""Regression checks: launch is idle and Stop cancels all AI work."""
import asyncio,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import app as companion
import httpx
class FakeBrowser:
 status='idle';process=None
 def __init__(self):self.closed=False;self.opened=False
 async def open(self,*args):self.opened=True
 async def close(self):self.closed=True
class FakeProcess:
 def terminate(self):pass
 def wait(self,timeout=None):return 0
class SafetyTests(unittest.IsolatedAsyncioTestCase):
 async def test_startup_never_opens_gpt_or_starts_watching(self):
  browser=FakeBrowser()
  with patch.object(companion,'browser',browser),patch.object(companion.subprocess,'Popen',return_value=FakeProcess()),patch.object(companion.subprocess,'check_output',return_value=''):
   async with companion.lifespan(companion.app):
    self.assertFalse(companion.state['running']);self.assertFalse(browser.opened)
  self.assertTrue(browser.closed)
 async def test_stop_cancels_preparation_worker_and_queue(self):
  browser=FakeBrowser();cancelled=asyncio.Event()
  async def preparing():
   try:await asyncio.sleep(3600)
   finally:cancelled.set()
  task=asyncio.create_task(preparing());worker=asyncio.create_task(asyncio.sleep(3600))
  await asyncio.sleep(0)
  old=companion.tasks;companion.tasks=[None,worker];companion.prepared.task=task
  companion.queue.put_nowait(True);companion.state.update(running=True,busy=True,queued=True)
  with patch.object(companion,'browser',browser):
   await companion.action('stop')
  self.assertTrue(cancelled.is_set());self.assertTrue(browser.closed)
  self.assertFalse(companion.state['running']);self.assertFalse(companion.state['busy']);self.assertTrue(companion.queue.empty())
  companion.tasks[1].cancel();await asyncio.gather(companion.tasks[1],return_exceptions=True);companion.tasks=old
 async def test_auth_and_loopback_recording_gate(self):
  transport=httpx.ASGITransport(app=companion.app,client=('192.168.1.42',1234))
  async with httpx.AsyncClient(transport=transport,base_url='http://local') as client:
   self.assertEqual((await client.get('/prepared')).status_code,403)
   self.assertEqual((await client.get('/media/video')).status_code,403)
   self.assertEqual((await client.post('/record/start',headers={'x-control-token':companion.token},json={'id':1,'pid':1})).status_code,403)
   response=await client.get('/prepared',headers={'x-control-token':companion.token})
   self.assertEqual(response.status_code,200);self.assertIn('stop_id',response.json())
if __name__=='__main__':unittest.main()
