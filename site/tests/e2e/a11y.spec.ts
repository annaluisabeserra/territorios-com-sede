import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PAGES = ["/", "/municipio/ba/salvador", "/municipio/ba/pau-brasil", "/mapa", "/calculadora", "/perguntas", "/indice", "/estado/ba", "/estado/ce", "/municipio/ce/sao-goncalo-do-amarante",
  "/busca?q=juazeiro", "/metodologia", "/faq", "/sobre", "/dados", "/escola", "/escola/ba/salvador", "/povos-e-comunidades"];

for (const path of PAGES) {
  test(`sem violações graves de acessibilidade: ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const serious = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious.map((v) => `${v.id}: ${v.help} (${v.nodes.length}) ${v.nodes[0]?.target}`)).toEqual([]);
  });
}

test("navegação por teclado alcança o conteúdo pelo link de pular", async ({ page }) => {
  await page.goto("/municipio/ba/salvador");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Pular para o conteúdo" })).toBeFocused();
});
