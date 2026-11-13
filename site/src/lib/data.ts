// Leitura dos dados em tempo de build (Node). No navegador, os mesmos arquivos são buscados via fetch.
import { readFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import type { Ficha, IndicatorDef, Resumo } from "./types";

const DATA = resolve(process.cwd(), "public/data");

function read<T>(...parts: string[]): T {
  return JSON.parse(readFileSync(join(DATA, ...parts), "utf8")) as T;
}

export interface UFEntry { sigla: string; code: string; name: string; slug: string; region: string }

export function ufs(): UFEntry[] {
  return read<{ ufs: UFEntry[] }>("index.json").ufs;
}

const resumoCache = new Map<string, Resumo>();
export function resumo(ufSlug: string): Resumo {
  if (!resumoCache.has(ufSlug)) resumoCache.set(ufSlug, read<Resumo>(ufSlug, "resumo.json"));
  return resumoCache.get(ufSlug)!;
}

export function ficha(ufSlug: string, slug: string): Ficha {
  return read<Ficha>(ufSlug, "municipios", `${slug}.json`);
}

export function indicators(): Record<string, IndicatorDef> {
  return read<Record<string, IndicatorDef>>("indicadores.json");
}

export function readJson<T>(...parts: string[]): T | null {
  const p = join(DATA, ...parts);
  return existsSync(p) ? (JSON.parse(readFileSync(p, "utf8")) as T) : null;
}

export const DEFAULT_UF = "ba";
