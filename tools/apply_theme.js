const fs = require("node:fs/promises");
const JSZip = require(require.resolve("jszip", { paths: [require.resolve("pptxgenjs")] }));

async function applyTheme(deckPath, theme) {
  const deck = await JSZip.loadAsync(await fs.readFile(deckPath));
  const scheme = Object.entries(theme.colors)
    .map(([slot, hex]) => `<a:${slot}><a:srgbClr val="${hex}"/></a:${slot}>`)
    .join("");
  const themeFiles = deck.file(/^ppt\/theme\/theme\d+\.xml$/);
  if (!themeFiles.length) throw new Error("PowerPoint theme parts are missing");
  for (const file of themeFiles) {
    const xml = await file.async("string");
    const updated = xml.replace(/<a:clrScheme\b[\s\S]*?<\/a:clrScheme>/,
      `<a:clrScheme name="${theme.name}">${scheme}</a:clrScheme>`);
    if (xml === updated && !xml.includes(scheme)) throw new Error(`Color scheme missing in ${file.name}`);
    deck.file(file.name, updated);
  }
  await fs.writeFile(deckPath, await deck.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}

module.exports = { applyTheme };
