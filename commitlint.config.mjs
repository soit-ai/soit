export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "type-enum": [
      2,
      "always",
      [
        "feat",
        "fix",
        "docs",
        "test",
        "refactor",
        "chore",
        "style",
        "build",
        "perf",
        "ci",
        "security",
        "hardening",
        "revert",
      ],
    ],
    "header-max-length": [2, "always", 100],
  },
};
