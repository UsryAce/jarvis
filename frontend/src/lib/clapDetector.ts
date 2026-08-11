export type ClapFrame = {
  detected: boolean;
  peak: number;
  rms: number;
  noiseFloor: number;
};

/** Detect a short broadband impulse against a slowly adapting room-noise floor. */
export class ClapDetector {
  private noiseFloor = 0.006;
  private previousRms = 0.006;
  private previousPeak = 0.012;
  private lastDetectionAt = Number.NEGATIVE_INFINITY;
  private framesSeen = 0;

  constructor(private readonly cooldownMs = 1800) {}

  process(samples: Float32Array, sensitivity: number, nowMs: number): ClapFrame {
    if (samples.length === 0) {
      return { detected: false, peak: 0, rms: 0, noiseFloor: this.noiseFloor };
    }

    let energy = 0;
    let peak = 0;
    let differenceEnergy = 0;
    let previousSample = samples[0];
    for (let index = 0; index < samples.length; index += 1) {
      const sample = samples[index];
      const absolute = Math.abs(sample);
      energy += sample * sample;
      if (absolute > peak) peak = absolute;
      if (index > 0) differenceEnergy += Math.abs(sample - previousSample);
      previousSample = sample;
    }

    const rms = Math.sqrt(energy / samples.length);
    this.framesSeen += 1;
    const averageDifference = differenceEnergy / Math.max(1, samples.length - 1);
    const normalizedSensitivity = Math.max(0, Math.min(1, sensitivity / 10));
    // Speech plosives and audio leaking through virtual mixer devices used to
    // satisfy the old, very low gates. Keep sensitivity useful while requiring
    // the sharper peak, crest, and attack of a real hand clap.
    const minimumPeak = 0.28 - normalizedSensitivity * 0.13;
    const minimumRms = 0.045 - normalizedSensitivity * 0.02;
    const relativeEnergyGate = 4.2 - normalizedSensitivity * 1.7;
    const crestGate = 3.2 - normalizedSensitivity;
    const attackGate = 2.8 - normalizedSensitivity;
    // The impulse only occupies a small fraction of a 1024-sample frame, so the
    // whole-frame difference average must remain low enough for normal mics.
    const differenceGate = 0.008 - normalizedSensitivity * 0.004;
    const crestFactor = peak / Math.max(rms, 0.0001);
    const rmsAttack = rms / Math.max(this.previousRms, this.noiseFloor, 0.0001);
    const peakAttack = peak / Math.max(this.previousPeak, this.noiseFloor * 2, 0.0001);
    const transientAttack = Math.max(rmsAttack, peakAttack);
    const detected =
      this.framesSeen > 12 &&
      nowMs - this.lastDetectionAt >= this.cooldownMs &&
      peak >= minimumPeak &&
      rms >= minimumRms &&
      rms >= this.noiseFloor * relativeEnergyGate &&
      crestFactor >= crestGate &&
      transientAttack >= attackGate &&
      averageDifference >= differenceGate;

    if (detected) {
      this.lastDetectionAt = nowMs;
    } else if (rms < Math.max(0.08, this.noiseFloor * 2.5)) {
      const adaptation = rms < this.noiseFloor ? 0.035 : 0.008;
      this.noiseFloor = Math.max(
        0.0015,
        Math.min(0.055, this.noiseFloor * (1 - adaptation) + rms * adaptation),
      );
    }

    this.previousRms = Math.max(0.0001, rms);
    this.previousPeak = Math.max(0.0001, peak);
    return { detected, peak, rms, noiseFloor: this.noiseFloor };
  }
}
