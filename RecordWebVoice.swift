import Foundation
import ScreenCaptureKit
import AVFoundation
import CoreMedia
class AudioRecorder: NSObject, SCStreamOutput {
 var writer: AVAssetWriter!
 var input: AVAssetWriterInput!
 var started = false
 var failed = false
 let queue = DispatchQueue(label: "citywalk.web.audio")
 func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
  guard type == .audio, CMSampleBufferDataIsReady(sampleBuffer), !failed else { return }
  if !started { writer.startWriting();writer.startSession(atSourceTime:CMSampleBufferGetPresentationTimeStamp(sampleBuffer));started=true }
  if input.isReadyForMoreMediaData { if !input.append(sampleBuffer) { failed=true } }
 }
}
@main struct Main {
 static func main() async {
  guard CommandLine.arguments.count == 3, let pid = Int32(CommandLine.arguments[1]) else { exit(2) }
  do {
   let content = try await SCShareableContent.excludingDesktopWindows(false,onScreenWindowsOnly:false)
   guard let app=content.applications.first(where:{$0.processID==pid}),let display=content.displays.first else { exit(3) }
   let recorder=AudioRecorder();let target=URL(fileURLWithPath:CommandLine.arguments[2])
   recorder.writer=try AVAssetWriter(outputURL:target,fileType:.m4a)
   recorder.input=AVAssetWriterInput(mediaType:.audio,outputSettings:[AVFormatIDKey:kAudioFormatMPEG4AAC,AVSampleRateKey:48000,AVNumberOfChannelsKey:2,AVEncoderBitRateKey:192000])
   recorder.input.expectsMediaDataInRealTime=true;recorder.writer.add(recorder.input)
   let config=SCStreamConfiguration();config.capturesAudio=true;config.excludesCurrentProcessAudio=true;config.sampleRate=48000;config.channelCount=2;config.width=2;config.height=2;config.minimumFrameInterval=CMTime(value:1,timescale:1)
   let filter=SCContentFilter(display:display,including:[app],exceptingWindows:[])
   let stream=SCStream(filter:filter,configuration:config,delegate:nil)
   try stream.addStreamOutput(recorder,type:.audio,sampleHandlerQueue:recorder.queue)
   try await stream.startCapture();print("READY");fflush(stdout)
   await withCheckedContinuation { (continuation:CheckedContinuation<Void,Never>) in DispatchQueue.global().async { _=FileHandle.standardInput.readData(ofLength:1);continuation.resume() } }
   try await stream.stopCapture()
   if recorder.started { recorder.input.markAsFinished();await recorder.writer.finishWriting() }
   if recorder.writer.status != .completed { exit(4) }
  } catch { fputs("Web audio recording failed\n",stderr);exit(5) }
 }
}
