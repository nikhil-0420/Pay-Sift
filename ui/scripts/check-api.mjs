const base = (process.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
const checks = [
  ["GET", "/health"],
  ["GET", "/runs"],
  ["GET", "/kill-matrix"],
  [
    "POST",
    "/break",
    { candidate_id: "reference", scenario: "duplicate_capture" },
  ],
  ["POST", "/repair", { candidate_id: "reference", failure_id: 0 }],
];
let errors = 0;
for (const [method, path, body] of checks) {
  try {
    const r = await fetch(base + path, {
      method,
      headers: body ? { "content-type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(path === "/repair" ? 180000 : 10000),
    });
    const t = await r.text();
    if (!r.ok) {
      if (path === "/repair" && (r.status === 403 || r.status === 503)) {
        console.log(
          `${method} ${path}: ${r.status} OK (expected response when live sandbox/model repair is blocked)`,
        );
      } else {
        console.error(`${method} ${path}: HTTP ${r.status} ${t.slice(0, 300)}`);
        errors++;
      }
    } else {
      let j;
      try {
        j = JSON.parse(t);
      } catch {}
      if (path === "/runs" && !Array.isArray(j)) {
        console.error("GET /runs expected an array");
        errors++;
      } else console.log(`${method} ${path}: ${r.status} OK`);
    }
  } catch (e) {
    console.error(`${method} ${path}: ${e.message}`);
    errors++;
  }
}
if (errors) process.exit(1);
