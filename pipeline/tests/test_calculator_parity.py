"""O arquivo de paridade versionado precisa ser exatamente o gerado pela calculadora Python atual.

Se este teste falhar, rode `uv run python -m pipeline.transform.parity`, confira o diff e versione o arquivo;
o Vitest então verifica o TypeScript contra os novos casos. Este teste não escreve nada no repositório.
"""

from pipeline.transform.parity import OUT, OUT_INDEX, generate, index_cases, serialize


def test_versioned_parity_file_matches_python():
    assert OUT.exists(), "rode: uv run python -m pipeline.transform.parity"
    assert OUT.read_text() == serialize(generate()), "calculator.parity.json desatualizado em relação ao Python"


def test_versioned_index_parity_file_matches_python():
    assert OUT_INDEX.read_text() == index_cases(), "priority.parity.json desatualizado em relação ao Python"
