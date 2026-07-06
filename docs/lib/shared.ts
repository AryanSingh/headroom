const gitUser = process.env.NEXT_PUBLIC_GIT_USER ?? "AryanSingh";
const gitRepo = process.env.NEXT_PUBLIC_GIT_REPO ?? "cutctx";
const gitBranch = process.env.NEXT_PUBLIC_GIT_BRANCH ?? "main";

export const docsRoute = "/docs";
export const docsContentRoute = "/content/docs";

export const gitConfig = {
  user: gitUser,
  repo: gitRepo,
  branch: gitBranch,
} as const;
