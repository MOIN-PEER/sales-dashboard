// Optional: refresh frontend/vendor/ from node_modules after `npm install`.
const fs = require("fs");
const path = require("path");
const root = path.resolve(__dirname, "..");
const copies = [
  ["node_modules/vue/dist/vue.global.prod.js", "frontend/vendor/vue.global.prod.js"],
  ["node_modules/chart.js/dist/chart.umd.js", "frontend/vendor/chart.umd.js"],
];
for (const [from, to] of copies) {
  fs.copyFileSync(path.join(root, from), path.join(root, to));
  console.log(`copied ${from} -> ${to}`);
}
