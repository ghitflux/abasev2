import { defineConfig } from "@kubb/core";
import { pluginClient } from "@kubb/plugin-client";
import { pluginOas } from "@kubb/plugin-oas";
import { pluginReactQuery } from "@kubb/plugin-react-query";
import { pluginTs } from "@kubb/plugin-ts";
import { pluginZod } from "@kubb/plugin-zod";

export default defineConfig({
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
