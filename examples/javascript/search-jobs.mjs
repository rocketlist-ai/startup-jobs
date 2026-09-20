import { createGunzip } from "node:zlib";
import { Readable } from "node:stream";
import readline from "node:readline";

const url = "https://github.com/rocketlist-ai/startup-jobs/releases/latest/download/jobs.jsonl.gz";
const response = await fetch(url);
if (!response.ok || !response.body) throw new Error(`Download failed: ${response.status}`);

const lines = readline.createInterface({
  input: Readable.fromWeb(response.body).pipe(createGunzip()),
  crlfDelay: Infinity,
});

for await (const line of lines) {
  const job = JSON.parse(line);
  if (/founder|strategy|operations/i.test(job.title ?? "") && /Germany/i.test(job.country ?? "")) {
    console.log(`${job.company_name} — ${job.title} — ${job.url}`);
  }
}

