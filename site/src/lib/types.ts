// Tipos dos arquivos públicos gerados pelo pipeline (data/public). Ver pipeline/transform/build.py.
export type Num = number | null;

export interface IndicatorDef {
  label: string;
  short: string;
  unit: "pct" | "count" | "number" | "rate_10k" | "rate_100k" | "brl" | "brl_pc" | "years" | "index" | "days" | "lhabdia" | "bool";
  direction: "higher_is_better" | "higher_is_worse" | "lower_is_worse" | "neutral";
  group: string;
  source: string;
  formula: string;
  limitations: string[];
  map?: boolean;
  palette?: "sequential" | "diverging";
}

export interface SourceStatus {
  status: "ok" | "stale" | "unavailable";
  status_reason: string;
  name: string | null;
  url: string | null;
  url_kind: "official" | "mirror" | null;
  reference_period: string | null;
  fetched_at: string | null;
  license: string | null;
  notes: string | null;
}

export interface ThermoShort { agua: string; esgoto: string; agua_ano: Num; esgoto_ano: Num }

export interface ResumoMunicipio {
  cod: string; nome: string; slug: string; ri: string; rim: string; semiarido: boolean | null;
  ind: Record<string, Num>; pct: Record<string, Num>; dims: Record<string, Num>;
  idx: Num; rank: Num; thermo: ThermoShort; sdw?: boolean;
}

export interface IndexInfo {
  weights: Record<string, number>;
  dimensions: Record<string, { label: string; weight: number; components: string[] }>;
  dims_available: string[];
  dims_missing: string[];
  fallbacks_used: Record<string, string>;
  min_dimensions_for_rank: number;
  required_dimensions?: string[];
  ranked: number;
}

export interface Resumo {
  uf: { sigla: string; nome: string; code: string; slug: string; region: string; preposicao?: string };
  generated_at: string;
  pipeline_version: string;
  sources: Record<string, SourceStatus>;
  flags: Record<string, boolean>;
  snis_year: Num;
  sinisa_years?: number[];
  health: { years: number[] | null; price_base: Num; period_label: string | null };
  index: IndexInfo;
  stats: Record<string, { median_uf: Num; median_br: Num; min: Num; max: Num; n: number }>;
  totals: Record<string, Num>;
  municipios: ResumoMunicipio[];
}

export interface Thermometer {
  service: "agua" | "esgoto"; target: number; status: "atingida" | "no_ritmo" | "atrasado" | "sem_dados";
  current: Num; current_year: Num; gap: Num; slope: Num; slope_low: Num; slope_high: Num;
  projected_year: Num; projected_year_low: Num; projected_year_high: Num; n_points: number; years: number[];
  uncertain: boolean; reason: string;
}

export interface Baseline {
  hospital_cost: Num; hospital_days: Num; school_days: Num; daily_income: Num; deaths?: Num; productive_years_lost?: Num;
}

export interface ImpactoCamada {
  label: string; pergunta: string; tipo: "observado" | "estimado" | "indicador"; premissa: string | null;
  baixo: Num; alto: Num; unidade: "brl" | "dias"; referencia: string | null; fonte: string; volume_m3?: number;
}
export interface Impacto {
  camadas: Record<"saude_sus" | "trabalho" | "vidas" | "escola" | "agua_perdida", ImpactoCamada>;
  total: { baixo: Num; alto: Num; por_pessoa_baixo: Num; por_pessoa_alto: Num; inclui: string[]; faltando: ("saude_sus" | "trabalho" | "vidas" | "agua_perdida")[]; alto_parcial: string[] };
  price_base: Num;
}

export interface Ficha {
  cod: string; nome: string; slug: string; uf: string; uf_nome: string;
  regiao_imediata: string; regiao_intermediaria: string; semiarido: boolean | null;
  resumo: string[];
  ind: Record<string, Num>;
  ind_ano: Record<string, Num>;
  ind_antigo: Record<string, [number, number]>;
  esgoto_sem_declaracao: boolean;
  series: Record<string, [number, number][]>;
  thermometer: { agua: Thermometer; esgoto: Thermometer };
  divergence: Record<string, { censo: number; snis: number; diff_pp: number; flag: boolean }>;
  impacto?: Impacto;
  health: null | {
    internacoes: number; valor: number; dias: number; obitos: Num; taxa_10mil: number; custo_per_capita: number;
    dias_6_17: Num; internacoes_menor5: Num; period: string;
    vetores: { internacoes: Num; valor: Num; dias: Num; dias_6_17: Num };
    by_year: [number, number, number][]; by_group: { group: string; label: string; layer: string; internacoes: number; valor: number }[];
  };
  calculator: { baseline: Baseline; baseline_vectors: Baseline | null; defaults: { reduction_pct: number; horizon_years: number; discount_rate: number } };
  communities: {
    pop_quilombola: Num; pop_quilombola_em_territorio: Num; pop_quilombola_lower_bound: boolean; pop_cor_indigena: Num;
    quilombola_pct_celulas_sigilo: Num; pop_indigena?: Num; retirado_a_pedido?: boolean; fonte_censo: string; fonte_tis: string; nota_territorio: string;
    ucs_uso_sustentavel?: { nome: string; categoria: string; esfera: string; ano_criacao: string | null; id_cnuc: string }[];
    terras_indigenas: { codigo_funai: string | null; ufs: string | null; data_ref: string | null; nome: string; etnia: string | null; fase: string | null; modalidade: string | null; area_ha_total: Num; pct_da_ti_no_municipio: number }[];
  };
  index: { score: Num; rank: Num; n_ranked: number; coverage: Num; dims: Record<string, Num>; components: Record<string, Num> };
  atuacao_sdw?: { localidade: string; papel: string; descricao: string; site: string; contato: string }[];
  suggestions: { id: string; title: string; why: string; contact: string }[];
  neighbors: { cod: string; nome: string; slug: string }[];
  generated_at: string;
}
