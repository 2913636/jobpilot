import { FlatCompat } from "eslint-flat-config-utils";

const compat = new FlatCompat();

export default [
  ...compat.extends("next/core-web-vitals"),
  {
    rules: {
      "@typescript-eslint/no-unused-vars": "warn",
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
  {
    ignores: [".next/**", "node_modules/**", "*.config.*"],
  },
];
