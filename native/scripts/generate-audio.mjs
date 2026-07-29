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
const noise = (index) => {
  const value = Math.sin(index * 12.9898 + 78.233) * 43758.5453;
  return (value - Math.floor(value)) * 2 - 1;
};

// A warm koto-like string with an intentionally short, woody attack.
const koto = (t, start, midi, length = 2.2) => {
  const age = t - start;
  if (age < 0 || age > length) return 0;
  const envelope = Math.exp(-2.0 * age) * Math.min(1, age * 90);
  const frequency = note(midi) * (1 + Math.exp(-14 * age) * .009);
  return envelope * (Math.sin(2 * Math.PI * frequency * age) * .68
    + Math.sin(2 * Math.PI * frequency * 2 * age) * .2
    + Math.sin(2 * Math.PI * frequency * 3 * age) * .08
    + noise(Math.floor(age * RATE)) * Math.exp(-42 * age) * .09);
};

// Breathier than a plain sine: a restrained shakuhachi-like lead.
const shakuhachi = (t, start, midi, length = 2.7) => {
  const age = t - start;
  if (age < 0 || age > length) return 0;
  const envelope = Math.min(1, age * 4) * Math.exp(-1.0 * age);
  const frequency = note(midi) * (1 + Math.sin(2 * Math.PI * 4.6 * age) * .006);
  return envelope * (Math.sin(2 * Math.PI * frequency * age) * .78
    + Math.sin(2 * Math.PI * frequency * 2 * age) * .09
    + noise(Math.floor(age * RATE * .37)) * .065);
};

// Hirajoshi-inspired scale: D Eb G A Bb. The sparse 24s phrase loops without a beat.
writeWav("dojo-loop.wav", 24, (t) => {
  const melody = [[.0, 69, 2.3], [3.0, 70, 1.9], [5.7, 74, 2.6], [9.1, 76, 1.8], [12.0, 74, 2.4], [15.2, 70, 2.0], [18.2, 69, 2.8], [21.4, 67, 2.2]];
  const strings = [[.0, 50], [1.5, 57], [4.4, 55], [7.3, 58], [10.5, 50], [13.3, 57], [16.1, 55], [19.0, 58], [22.0, 50]];
  let signal = 0;
  for (const [start, midi, length] of melody) signal += shakuhachi(t, start, midi, length);
  for (const [start, midi] of strings) {
    signal += koto(t, start, midi);
    signal += koto(t, start + .46, midi + 7, 1.6) * .52;
  }
  const bed = Math.sin(2 * Math.PI * note(38) * t) * .055 + Math.sin(2 * Math.PI * note(45) * t) * .03;
  return (signal * .19) + bed;
});

writeWav("tap.wav", .16, (t) => koto(t, 0, 81, .18) * .72);
writeWav("correct.wav", .55, (t) => {
  const sequence = [[0, 74], [.15, 76], [.31, 81]];
  return sequence.reduce((sum, [start, midi]) => sum + koto(t, start, midi, .42), 0) * .38;
});
writeWav("wrong.wav", .42, (t) => {
  const frequency = 235 - 80 * t;
  return (Math.sin(2 * Math.PI * frequency * t) + noise(Math.floor(t * RATE * 2)) * .07) * Math.exp(-6.5 * t) * .2;
});
writeWav("complete.wav", 1.25, (t) => {
  const sequence = [[0, 62], [.14, 67], [.3, 69], [.49, 74], [.72, 81]];
  return sequence.reduce((sum, [start, midi]) => sum + koto(t, start, midi, .72), 0) * .32;
});

console.log(`Generated original audio in ${OUTPUT}`);
