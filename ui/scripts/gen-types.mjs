import fs from "node:fs";
const schema = JSON.parse(
  fs.readFileSync("public/data/run_schema.json", "utf8"),
);
const keys = Object.keys(schema.properties || {});
const out = `// Generated from public/data/run_schema.json. Unknown keys remain tolerated.\nexport interface RunGenerated {\n${keys.map((k) => `  ${k}${(schema.required || []).includes(k) ? "" : "?"}: ${k === "failures" ? "unknown[]" : k === "seeds" ? "number[]" : "unknown"};`).join("\n")}\n  [key:string]: unknown;\n}\n`;
fs.mkdirSync("src/types", { recursive: true });
fs.writeFileSync("src/types/run.generated.ts", out);
console.log(`Generated run.generated.ts with ${keys.length} schema fields.`);
