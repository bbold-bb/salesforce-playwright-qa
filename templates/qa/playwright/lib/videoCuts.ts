import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';

// Dead time in a video: a wait the script marks as waiting, such as a mail arriving, the email
// switch in Setup or a page loading, is cut down to a second at each end once the run is over. Nothing else is cut, so
// cards, results and the time Salesforce takes to do what a step clicked stay whole. The uncut video is kept on this machine.
const KEEP = 1; // seconds left at each end of a wait
type Cut = { from: number; to: number };
type Video = { file: string; startedAt: number; cuts: Cut[] };
const videos: Video[] = [];
let recording: Video | null = null;

export function videoStarted(file: string) {
  recording = { file, startedAt: Date.now(), cuts: [] };
  videos.push(recording);
}
export function videoStopped() {
  recording = null;
}

// Runs a wait that's nothing to watch. Outside a video it only runs it.
export async function waiting<T>(wait: () => Promise<T>): Promise<T> {
  const video = recording;
  const from = Date.now();
  try {
    return await wait();
  } finally {
    if (video) video.cuts.push({ from: (from - video.startedAt) / 1000, to: (Date.now() - video.startedAt) / 1000 });
  }
}

// The cuts as stretches to drop: waits that overlap or touch count as one, and only what's left after KEEP at each end goes.
export function dropped(cuts: Cut[]): Cut[] {
  const merged: Cut[] = [];
  for (const c of [...cuts].sort((a, b) => a.from - b.from)) {
    const last = merged[merged.length - 1];
    if (last && c.from <= last.to + 0.5) last.to = Math.max(last.to, c.to);
    else merged.push({ ...c });
  }
  return merged.map((c) => ({ from: c.from + KEEP, to: c.to - KEEP })).filter((c) => c.to - c.from >= 1);
}

// Cuts each of the run's videos. Returns a line for the run summary per video that was cut. Without ffmpeg, or if it fails,
// the video stays as recorded.
export function cutVideos(uncutDir: string): string[] {
  const lines: string[] = [];
  for (const v of videos.splice(0)) {
    const drop = dropped(v.cuts);
    if (!drop.length || !fs.existsSync(v.file)) continue;
    const name = path.basename(v.file);
    const keep: string[] = [];
    let at = 0;
    for (const d of drop) { keep.push(`trim=${at.toFixed(2)}:${d.from.toFixed(2)}`); at = d.to; }
    keep.push(`trim=start=${at.toFixed(2)}`);
    const filter = `[0:v]fps=25,split=${keep.length}${keep.map((_, i) => `[s${i}]`).join('')};` +
      keep.map((k, i) => `[s${i}]${k},setpts=PTS-STARTPTS[k${i}]`).join(';') + ';' + keep.map((_, i) => `[k${i}]`).join('') + `concat=n=${keep.length}[out]`;
    const out = `${v.file}.cut.webm`;
    try {
      execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', v.file, '-filter_complex', filter, '-map', '[out]', '-c:v', 'libvpx-vp9', '-crf', '31', '-b:v', '0',
        '-deadline', 'realtime', '-cpu-used', '5', '-row-mt', '1', out], { stdio: ['ignore', 'ignore', 'pipe'], maxBuffer: 64 * 1024 * 1024 });
      fs.mkdirSync(uncutDir, { recursive: true });
      fs.renameSync(v.file, path.join(uncutDir, name));
      fs.renameSync(out, v.file);
      const seconds = Math.round(drop.reduce((n, d) => n + d.to - d.from, 0));
      lines.push(`${name}: ${seconds} seconds of waiting cut, in ${drop.length} place${drop.length === 1 ? '' : 's'} (mail arriving, the email setting, pages loading)`);
    } catch (e: any) {
      fs.rmSync(out, { force: true });
      console.log(`Video ${name} left as recorded: ffmpeg couldn't cut it (${String(e?.stderr ?? e?.message).split('\n')[0]}).`);
    }
  }
  return lines;
}
