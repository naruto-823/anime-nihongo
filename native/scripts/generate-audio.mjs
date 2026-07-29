import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const OUTPUT = resolve(ROOT, "assets/audio");
const RATE = 22050;

mkdirSync(OUTPUT, { recursive: true });

function writeWav(name, seconds, sample) {
  const count = Math.floor(RATE * seconds);
  const wav = Buffer.alloc(44 + count * 2);
  wav.write("RIFF", 0); wav.writeUInt32LE(36 + count * 2, 4); wav.write("WAVE", 8);
  wav.write("fmt ", 12); wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22); wav.writeUInt32LE(RATE, 24); wav.writeUInt32LE(RATE * 2, 28);
  wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34); wav.write("data", 36);
  wav.writeUInt32LE(count * 2, 40);
  for (let i = 0; i < count; i += 1) {
    const value = Math.max(-1, Math.min(1, sample(i / RATE, i, count)));
    wav.writeInt16LE(Math.round(value * 32767), 44 + i * 2);
  }
  writeFileSync(resolve(OUTPUT, name), wav);
}

const note = (midi) => 440 * 2 ** ((midi - 69) / 12);
const pluck = (t, start, midi, length = 1.4) => {
  const age = t - start;
  if (age < 0 || age > length) return 0;
  const envelope = Math.exp(-3.1 * age) * Math.min(1, age * 55);
  const frequency = note(midi);
  return envelope * (Math.sin(2 * Math.PI * frequency * age) * .72
    + Math.sin(2 * Math.PI * frequency * 2.01 * age) * .18
    + Math.sin(2 * Math.PI * frequency * 3.98 * age) * .1);
};

writeWav("dojo-loop.wav", 16, (t) => {
  const melody = [69, 72, 74, 76, 74, 72, 69, 67, 64, 67, 69, 72, 69, 67, 64, 62];
  let signal = 0;
  for (let beat = 0; beat < melody.length; beat += 1) signal += pluck(t, beat, melody[beat]);
  const roots = [45, 41, 43, 40];
  for (let bar = 0; bar < 4; bar += 1) {
    const age = t - bar * 4;
    if (age >= 0 && age < 4) {
      const swell = Math.sin(Math.PI * age / 4) ** 2;
      signal += .25 * swell * Math.sin(2 * Math.PI * note(roots[bar]) * age);
      signal += .1 * swell * Math.sin(2 * Math.PI * note(roots[bar] + 7) * age);
    }
  }
  return signal * .23;
});

writeWav("tap.wav", .12, (t) => Math.sin(2 * Math.PI * (620 - 900 * t) * t) * Math.exp(-30 * t) * .5);
writeWav("correct.wav", .55, (t) => {
  const sequence = [[0, 72], [.13, 76], [.27, 79]];
  return sequence.reduce((sum, [start, midi]) => sum + pluck(t, start, midi, .28), 0) * .42;
});
writeWav("wrong.wav", .42, (t) => {
  const frequency = 180 - 70 * t;
  return Math.sin(2 * Math.PI * frequency * t) * Math.exp(-5.5 * t) * .32;
});
writeWav("complete.wav", 1.25, (t) => {
  const sequence = [[0, 60], [.16, 64], [.32, 67], [.55, 72], [.76, 76]];
  return sequence.reduce((sum, [start, midi]) => sum + pluck(t, start, midi, .65), 0) * .34;
});

console.log(`Generated original audio in ${OUTPUT}`);
