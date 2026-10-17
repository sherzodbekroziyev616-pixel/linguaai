let audioContext: AudioContext | null = null

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined' || !window.AudioContext) return null
  audioContext ??= new window.AudioContext()
  if (audioContext.state === 'suspended') void audioContext.resume()
  return audioContext
}

function playTone(frequency: number, startAt: number, duration: number, volume: number): void {
  const context = getAudioContext()
  if (!context) return

  const oscillator = context.createOscillator()
  const gain = context.createGain()
  oscillator.type = 'sine'
  oscillator.frequency.setValueAtTime(frequency, startAt)
  gain.gain.setValueAtTime(0.0001, startAt)
  gain.gain.exponentialRampToValueAtTime(volume, startAt + 0.008)
  gain.gain.exponentialRampToValueAtTime(0.0001, startAt + duration)
  oscillator.connect(gain)
  gain.connect(context.destination)
  oscillator.start(startAt)
  oscillator.stop(startAt + duration)
}

export function playUiClick(): void {
  const context = getAudioContext()
  if (context) playTone(720, context.currentTime, 0.045, 0.025)
}

export function emitUiChime(): void {
  window.dispatchEvent(new Event('linguaai:chime'))
}

export function playUiChime(): void {
  const context = getAudioContext()
  if (!context) return
  playTone(587.33, context.currentTime, 0.16, 0.035)
  playTone(880, context.currentTime + 0.09, 0.22, 0.03)
}
