import { expect, test } from "@playwright/test";

test("home mostra manifesto, busca e números com fonte", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("a sede tem endereço");
  await expect(page.locator(".numbers .card")).toHaveCount(3);
  await expect(page.locator(".numbers .source").first()).not.toBeEmpty();
});

test("busca encontra município sem acento e leva à ficha", async ({ page }) => {
  await page.goto("/busca?q=feira de santana");
  await page.getByRole("link", { name: "Feira de Santana" }).first().click();
  await expect(page).toHaveURL(/\/municipio\/ba\/feira-de-santana/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Feira de Santana");
});

test("busca sem resultado sugere alternativas", async ({ page }) => {
  await page.goto("/busca?q=xyzwq");
  await expect(page.getByText("Nada encontrado")).toBeVisible();
});

test("ficha tem seções, fontes, termômetro e 'sem dado' em vez de zero", async ({ page }) => {
  await page.goto("/municipio/ba/salvador");
  for (const id of ["indicadores", "meta2033", "saude", "comunidades", "prioridade", "agir", "fontes"]) {
    await expect(page.locator(`#${id}`)).toBeVisible();
  }
  await expect(page.getByText("Termômetro 2033")).toBeVisible();
  await expect(page.locator("table").first()).toContainText("sem dado");
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", /\/og\/ba\/salvador\.png$/);
});

test("calculadora com dados manuais calcula e gera link compartilhável", async ({ page }) => {
  await page.goto("/calculadora?uf=ba&m=salvador");
  await page.locator("#manual-box summary").click();
  await page.fill("#m-cost", "100000");
  await page.fill("#m-days", "1000");
  await page.fill("#m-inc", "50");
  await page.getByRole("button", { name: "50%", exact: true }).click();
  await expect(page.locator("#out")).toContainText("Dados informados por você");
  await expect(page.locator("#out")).toContainText("R$ 75 mil");
  await expect(page).toHaveURL(/r=50/);
});

test("cenário SDW aparece com o rótulo de validação", async ({ page }) => {
  await page.goto("/calculadora");
  await page.getByRole("button", { name: /92%/ }).click();
  await expect(page.locator("#sdw-note")).toContainText("em validação independente");
});

test("perguntas guiadas respondem e o link reproduz a pergunta", async ({ page }) => {
  await page.goto("/perguntas?m=ranking&i=snis_agua_pct&r=todas&f=semiarido&o=asc&n=5&uf=ba");
  await expect(page.locator("#answer h2")).toContainText("Semiárido");
  await expect(page.locator("#answer .bar")).toHaveCount(5);
});

test("mapa carrega legenda e tabela alternativa", async ({ page }) => {
  await page.goto("/mapa");
  await expect(page.locator("#legend li").first()).toBeVisible();
  await page.locator(".tabled summary").click();
  await expect(page.locator("#tbl tbody tr")).toHaveCount(417);
});

test("índice explica por que não ranqueia quando faltam dimensões", async ({ page }) => {
  await page.goto("/indice");
  await expect(page.locator("#state")).toContainText(/ranqueados|ainda não pode ser calculado/);
});

test("página da escola e FAQ com 20+ perguntas", async ({ page }) => {
  await page.goto("/escola/ba/juazeiro");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Juazeiro");
  await page.goto("/faq");
  expect(await page.locator("details.q").count()).toBeGreaterThanOrEqual(20);
});

test("nenhuma ficha mostra 'None', 'nan' ou caractere corrompido", async ({ page }) => {
  for (const m of ["abaira", "tanque-novo", "pau-brasil", "salvador"]) {
    await page.goto(`/municipio/ba/${m}`);
    const text = await page.locator("main").innerText();
    expect(text).not.toMatch(/\bNone\b|\bnan%?|¿|undefined|∞/i);
  }
});

test("panorama estadual: trilha da ficha leva ao estado e o mapa mostra a atuação do Instituto SDW", async ({ page }) => {
  await page.goto("/municipio/ce/sao-goncalo-do-amarante");
  await expect(page.getByText("O Instituto SDW está aqui")).toBeVisible();
  await page.getByRole("navigation", { name: "Trilha" }).getByRole("link", { name: "Ceará" }).click();
  await expect(page).toHaveURL(/\/estado\/ce/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Água e esgoto no Ceará");
  await expect(page.getByRole("button", { name: /Salvar em PDF/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "São Gonçalo do Amarante" }).first()).toBeVisible();
});
