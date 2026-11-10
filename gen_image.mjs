// Article illustration generator using the official Google Gen AI SDK (https://github.com/googleapis/js-genai)
// Usage: node gen_image.mjs <output-file> "<english prompt>"      env: GEMINI_API_KEY, optional GENAI_IMAGE_MODEL, GENAI_TIMEOUT_S
// It discovers the image models your key can use (Gemini image models), tries up to 3 in order and writes the first image it gets.
import { GoogleGenAI } from '@google/genai';
import fs from 'node:fs';

const [, , out, ...rest] = process.argv;
const prompt = rest.join(' ').trim();
const key = process.env.GEMINI_API_KEY;
if (!key || !out || !prompt) {
  console.error('usage: GEMINI_API_KEY=... node gen_image.mjs <out-file> "<prompt>"');
  process.exit(2);
}
const ai = new GoogleGenAI({ apiKey: key });
const log = (...a) => console.error('[genai]', ...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// hard deadline for this whole image (default 130 s): a rate-limited API must never stall the pipeline
setTimeout(() => { log('deadline reached, giving up on this image'); process.exit(1); }, (Number(process.env.GENAI_TIMEOUT_S) || 130) * 1000).unref();

async function listModels() {
  const found = [];
  try {
    const pager = await ai.models.list();
    for await (const m of pager) {
      found.push({ name: String(m.name || '').replace(/^models\//, ''), acts: m.supportedActions || m.supportedGenerationMethods || [] });
    }
  } catch (e) {
    log('model listing failed, using built-in names:', e.message);
  }
  return found;
}

function candidates(models) {
  // With a normal Gemini API key the supported path is generateContent on Gemini image models.
  // (generateImages / Imagen is Vertex-only in the current SDK, so it is used only if you force it with GENAI_IMAGE_MODEL.)
  const gem = models.filter((m) => /image/.test(m.name) && !/imagen/.test(m.name) && m.acts.includes('generateContent')).map((m) => m.name)
    .sort((a, b) => Number(/preview|exp/.test(a)) - Number(/preview|exp/.test(b)) || b.localeCompare(a));
  const list = [process.env.GENAI_IMAGE_MODEL, ...gem];
  if (!gem.length) list.push('gemini-2.5-flash-image');
  return [...new Set(list.filter(Boolean))].slice(0, 3);
}

async function viaImagen(model) {
  const r = await ai.models.generateImages({ model, prompt, config: { numberOfImages: 1, aspectRatio: '16:9' } });
  const b64 = r.generatedImages?.[0]?.image?.imageBytes;
  if (!b64) throw new Error('no image in response');
  return Buffer.from(b64, 'base64');
}

async function viaGemini(model) {
  const attempts = [
    { responseModalities: ['IMAGE'], imageConfig: { aspectRatio: '16:9' } },
    { responseModalities: ['IMAGE'] },
    { responseModalities: ['TEXT', 'IMAGE'] },
  ];
  let last;
  for (const config of attempts) {
    try {
      const r = await ai.models.generateContent({ model, contents: prompt, config });
      const part = (r.candidates?.[0]?.content?.parts || []).find((p) => p.inlineData?.data);
      if (part) return Buffer.from(part.inlineData.data, 'base64');
      last = new Error('no image in response');
    } catch (e) {
      last = e;
      if (!/imageConfig|responseModalities|INVALID_ARGUMENT|400/.test(String(e.message))) throw e;
    }
  }
  throw last;
}

const models = await listModels();
const order = candidates(models);
log('trying models:', order.join(', '));
for (const model of order) {
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const buf = /imagen/.test(model) ? await viaImagen(model) : await viaGemini(model);
      if (buf.length < 5000) throw new Error('image too small');
      fs.writeFileSync(out, buf);
      log('ok with', model, `(${buf.length} bytes)`);
      process.exit(0);
    } catch (e) {
      const msg = String(e.message || e).slice(0, 220);
      log(`${model} attempt ${attempt} failed: ${msg}`);
      if (attempt === 1 && /429|RESOURCE_EXHAUSTED|503|UNAVAILABLE/.test(msg)) { await sleep(8000); continue; }
      break;
    }
  }
}
log('no model produced an image');
process.exit(1);
