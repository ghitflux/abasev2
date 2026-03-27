import { defineConfig } from "@kubb/core";
import { pluginClient } from "@kubb/plugin-client";
import { pluginOas } from "@kubb/plugin-oas";
import { pluginReactQuery } from "@kubb/plugin-react-query";
import { pluginTs } from "@kubb/plugin-ts";
import { pluginZod } from "@kubb/plugin-zod";

const inputPath = process.env.KUBB_INPUT_PATH || "../../backend/schema.yaml";
const outputPath = process.env.KUBB_OUTPUT_PATH || "./src/gen";
const cleanOutput = process.env.KUBB_CLEAN === "true";

export default defineConfig({
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
