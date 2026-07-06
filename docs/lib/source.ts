import { loader } from "fumadocs-core/source";
import { docs } from "../.source/server";

export const source = loader({
  source: docs.toFumadocsSource(),
  baseUrl: "/docs",
});

type Page = ReturnType<typeof source.getPages>[number];

function pageSegments(page: Page): string[] {
  return page.slugs;
}

export function getPageMarkdownUrl(page: Page) {
  const segments = pageSegments(page);
  return {
    segments,
    url: `/llms.mdx/docs/${segments.join("/")}`,
  };
}

export function getPageImage(page: Page) {
  const segments = pageSegments(page);
  return {
    segments,
    url: `/og/docs/${segments.join("/")}`,
  };
}

export async function getLLMText(page: Page): Promise<string> {
  const title = page.data.title ?? "";
  const description = page.data.description ?? "";
  const body =
    typeof page.data.getText === "function" ? await page.data.getText("processed") : "";

  return [title ? `# ${title}` : "", description, body].filter(Boolean).join("\n\n");
}
