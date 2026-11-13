import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

// Conteúdo editável pelo Decap CMS (public/admin/config.yml).
const faq = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/faq" }),
  schema: z.object({ question: z.string(), order: z.number(), category: z.string() }),
});
const escola = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/escola" }),
  schema: z.object({ title: z.string(), order: z.number(), level: z.string(), duration: z.string(), summary: z.string() }),
});
const paginas = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/paginas" }),
  schema: z.object({ title: z.string(), description: z.string() }),
});
export const collections = { faq, escola, paginas };
