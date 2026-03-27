const { defineConfig } = require("@kubb/core");
const { pluginClient } = require("@kubb/plugin-client");
const { pluginOas } = require("@kubb/plugin-oas");
const { pluginReactQuery } = require("@kubb/plugin-react-query");
const { pluginTs } = require("@kubb/plugin-ts");
const { pluginZod } = require("@kubb/plugin-zod");

const inputPath = process.env.KUBB_INPUT_PATH || "../../backend/schema.yaml";
const outputPath = process.env.KUBB_OUTPUT_PATH || "./src/gen";
const cleanOutput = process.env.KUBB_CLEAN === "true";

module.exports = defineConfig({
  input: {
    path: inputPath,
  },
  output: {
    path: outputPath,
    clean: cleanOutput,
    format: "prettier",
  },
  plugins: [
    pluginOas({ validate: false }),
    pluginTs({ output: { path: "./models" } }),
    pluginClient({ output: { path: "./client" } }),
    pluginReactQuery({ output: { path: "./hooks" } }),
    pluginZod({ output: { path: "./zod" }, importPath: "zod" }),
  ],
});
