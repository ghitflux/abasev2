const { defineConfig } = require("@kubb/core");
const { pluginClient } = require("@kubb/plugin-client");
const { pluginOas } = require("@kubb/plugin-oas");
const { pluginReactQuery } = require("@kubb/plugin-react-query");
const { pluginTs } = require("@kubb/plugin-ts");
const { pluginZod } = require("@kubb/plugin-zod");

module.exports = defineConfig({
  input: {
    path: "../../backend/schema.yaml",
  },
  output: {
    path: "./src/gen",
    clean: true,
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
