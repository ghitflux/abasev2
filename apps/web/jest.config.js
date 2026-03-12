const nextJest = require("next/jest.js");

const createJestConfig = nextJest({
  dir: "./",
});

const customJestConfig = {
  testEnvironment: "jest-environment-jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  roots: ["<rootDir>/src"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
  modulePathIgnorePatterns: ["<rootDir>/.next/"],
  testPathIgnorePatterns: ["<rootDir>/.next/", "<rootDir>/node_modules/"],
};

module.exports = createJestConfig(customJestConfig);
