// Post-build: add package.json to CJS output so Node treats it as CommonJS
import { writeFileSync, mkdirSync } from "fs";
mkdirSync("dist/cjs", { recursive: true });
writeFileSync("dist/cjs/package.json", JSON.stringify({ type: "commonjs" }) + "\n");
