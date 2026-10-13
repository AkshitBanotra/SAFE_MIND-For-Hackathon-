/** Capture microphone audio and emit mono float32 frames at 16 kHz / 512 samples. */
export async function startVoiceAudio(
  stream: MediaStream,
  onFrame: (frame: Float32Array) => void,
): Promise<() => Promise<void>> {
  const context = new AudioContext()
  const workletSource = `
    class Mono16kProcessor extends AudioWorkletProcessor {
      constructor(options) {
        super();
        this.ratio = sampleRate / 16000;
        this.samples = [];
        this.position = 0;
        this.frame = new Float32Array(512);
        this.frameOffset = 0;
      }
      process(inputs) {
        const channels = inputs[0];
        if (!channels || channels.length === 0) return true;
        const length = channels[0].length;
        for (let i = 0; i < length; i++) {
          let mono = 0;
          for (let channel = 0; channel < channels.length; channel++) mono += channels[channel][i] || 0;
          this.samples.push(mono / channels.length);
        }
        while (this.position + 1 < this.samples.length) {
          const left = Math.floor(this.position);
          const fraction = this.position - left;
          const sample = this.samples[left] * (1 - fraction) + this.samples[left + 1] * fraction;
          this.frame[this.frameOffset++] = sample;
          this.position += this.ratio;
          if (this.frameOffset === 512) {
            const frame = this.frame;
            this.port.postMessage(frame, [frame.buffer]);
            this.frame = new Float32Array(512);
            this.frameOffset = 0;
          }
        }
        const consumed = Math.floor(this.position);
        if (consumed > 0) {
          this.samples = this.samples.slice(consumed);
          this.position -= consumed;
        }
        return true;
      }
    }
    registerProcessor('mono-16k-512', Mono16kProcessor);
  `
  const moduleUrl = URL.createObjectURL(new Blob([workletSource], { type: 'text/javascript' }))
  try {
    await context.audioWorklet.addModule(moduleUrl)
    await context.resume()
  } catch (error) {
    await context.close()
    throw error
  } finally {
    URL.revokeObjectURL(moduleUrl)
  }

  const source = context.createMediaStreamSource(stream)
  const processor = new AudioWorkletNode(context, 'mono-16k-512', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] })
  const mute = context.createGain()
  mute.gain.value = 0
  processor.port.onmessage = (event: MessageEvent<Float32Array>) => onFrame(event.data)
  source.connect(processor)
  processor.connect(mute)
  mute.connect(context.destination)

  return async () => {
    processor.port.onmessage = null
    processor.disconnect()
    mute.disconnect()
    source.disconnect()
    stream.getTracks().forEach((track) => track.stop())
    if (context.state !== 'closed') await context.close()
  }
}
