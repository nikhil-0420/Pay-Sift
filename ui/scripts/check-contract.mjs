import fs from "node:fs";
import path from "node:path";
import Ajv from "ajv";

const root = "public/data";
let schema;
try {
  schema = JSON.parse(
    fs.readFileSync(path.join(root, "run_schema.json"), "utf8"),
  );
} catch (e) {
  console.error(`Schema unavailable: ${e.message}`);
  process.exit(1);
}
const ajv = new Ajv({ allErrors: true, strict: false });
const validate = ajv.compile(schema);
const files = [];
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(file);
    else if (
      entry.name.endsWith(".json") &&
      ![
        "sample.json",
        "real_example.json",
        "kill_matrix.sample.json",
        "kill_matrix.json",
        "scenario_verdicts.json",
        "status.json",
        "featured.json",
        "index.json",
        "grounding.json",
      ].includes(entry.name)
    )
      files.push(file);
  }
}
walk(path.join(root, "runs"));
let bad = 0;
for (const file of files) {
  const data = JSON.parse(fs.readFileSync(file, "utf8"));
  if (!validate(data)) {
    bad++;
    console.error(
      `FAIL ${file}: ${ajv.errorsText(validate.errors, { separator: "; " })}`,
    );
  }
}
const groundingPath = path.join(root, "runs", "grounding.json");
const groundingSchemaPath = path.join(
  root,
  "contract",
  "grounding_schema.json",
);
if (fs.existsSync(groundingPath) && fs.existsSync(groundingSchemaPath)) {
  try {
    const grounding = JSON.parse(fs.readFileSync(groundingPath, "utf8"));
    const groundingSchema = JSON.parse(
      fs.readFileSync(groundingSchemaPath, "utf8"),
    );
    const validateGrounding = ajv.compile(groundingSchema);
    if (!validateGrounding(grounding)) {
      bad++;
      console.error(
        `FAIL ${groundingPath}: ${ajv.errorsText(validateGrounding.errors, { separator: "; " })}`,
      );
    } else
      console.log(
        "Checked grounding.json against contract/grounding_schema.json.",
      );
  } catch (e) {
    bad++;
    console.error(`FAIL grounding contract: ${e.message}`);
  }
} else
  console.log(
    "Grounding contract check skipped (grounding.json or contract/grounding_schema.json absent).",
  );
console.log(`Checked ${files.length} run file(s); ${bad} schema error(s).`);
if (bad) process.exit(1);
