// Converte os agregados do Worker numa Issue para revisão humana (workflow learning-report.yml).
import { readFileSync } from "node:fs";
const r = JSON.parse(readFileSync(process.argv[2], "utf8"));
const by = (t) => r.eventos.filter((e) => e.tipo === t).slice(0, 25);
const table = (rows) => rows.length ? ["| Ocorrências | Detalhe |", "|---:|---|", ...rows.map((e) => `| ${e.total} | \`${e.chave}\` |`)].join("\n") : "_Nenhum registro._";
console.log(`# Relatório de aprendizado: ${r.mes}

Dados anônimos e agregados. **Nada aqui é publicado automaticamente**: marque o que deve virar mudança e abra um PR.

## Buscas sem resultado (termos que a busca deveria entender)
${table(by("search_no_result"))}

- [ ] Adicionar sinônimos em \`site/src/lib/search.ts\`
- [ ] Criar perguntas no FAQ para os temas recorrentes

## Perguntas guiadas mais montadas (indicadores mais procurados)
${table(by("guided_question"))}

- [ ] Promover as mais frequentes a perguntas prontas (\`site/src/lib/questions.ts\`)

## Cenários da calculadora
${table(by("calc_scenario"))}
`);
