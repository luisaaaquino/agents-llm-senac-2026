"""
§5.4 — as três causas de esquecimento, executadas (não descritas).

  1. contradição: o mesmo fato em duas datas -> vence o carimbo mais novo,
     o antigo fica em `substituiu`; fato com condição diferente não empata.
  2. decaimento: episódio de 200 dias é rebaixado; de 400 dias é removido.
  3. remoção: grava tudo para um titular de teste numa execução REAL do
     grafo, mostra que o comportamento mudou, remove, mostra que voltou,
     e roda a varredura independente (scripts/verificar_remocao.py).

    python scripts/demo_memoria.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, memoria, remocao  # noqa: E402
from src.casos import CASOS  # noqa: E402
from src.nos_anuncio import iniciar_b  # noqa: E402

TITULAR = "V-TESTE"


def contradicao() -> dict:
    e = "vendedor:V-090"
    memoria.gravar_fato(e, "bairro_retirada", "Santo Amaro", fonte="anuncio:antigo",
                        data="2026-06-10T10:00:00")
    r = memoria.gravar_fato(e, "bairro_retirada", "Campo Grande", fonte="anuncio:novo",
                            data="2026-09-02T10:00:00")
    repetido = memoria.gravar_fato(e, "bairro_retirada", "Campo Grande", fonte="anuncio:novo")
    memoria.gravar_fato(e, "bairro_retirada", "Santo Amaro", fonte="anuncio:outro",
                        condicao="itens pequenos", data="2026-09-05T10:00:00")
    return {"gravacao_nova": r, "gravacao_repetida": repetido, "leitura": memoria.ler_fatos(e)}


def decaimento() -> dict:
    hoje = datetime.now()
    for dias in (10, 200, 400):
        memoria.gravar_episodio("V-091", "mesa", "Santo Amaro", "publicado", "nenhuma",
                                f"[{dias} dias atrás] mesa de madeira, Santo Amaro, publicada",
                                data=(hoje - timedelta(days=dias)).isoformat(timespec="seconds"))
    rotina = memoria.rotina_decaimento(hoje)
    restantes = memoria.ler_episodios("mesa", "mesa de madeira em Santo Amaro", k=5)
    return {"rotina": rotina, "restantes": [{k: e[k] for k in ("resumo", "rebaixado", "similaridade")}
                                            for e in restantes if e["vendedor_id"] == "V-091"]}


def remocao_completa() -> dict:
    from cli import rodar_caso
    # Duas execuções reais: a do caso 4 grava indício, anúncio aguardando
    # moderação, checkpoint e log; a do caso 1 grava fato semântico
    # (bairro_retirada) e episódio — juntas passam por todas as escritas.
    rodar_caso(replace(CASOS["04_avaria_negada"], nome="memoria_titular_teste_a", usuario_id=TITULAR))
    rodar_caso(replace(CASOS["01_simples"], nome="memoria_titular_teste_b", usuario_id=TITULAR,
                       decisoes=[(TITULAR, {"acao": "aprovar"})]))
    sonda = {"usuario_id": TITULAR, "categoria_mencionada": "geladeira",
             "texto_turno": "vendo outra geladeira", "mensagens": [{"quem": "usuario", "texto": "x"}]}
    antes = iniciar_b(sonda)["trajetoria"][0]["memoria_recuperada"]
    relatorio = remocao.remover_titular(TITULAR)
    depois = iniciar_b(sonda)["trajetoria"][0]["memoria_recuperada"]
    varredura = subprocess.run([sys.executable, str(config.ROOT / "scripts" / "verificar_remocao.py"),
                                TITULAR], capture_output=True, text=True, encoding="utf-8")
    return {"memoria_recuperada_antes_da_remocao": antes, "relatorio_da_remocao": relatorio,
            "memoria_recuperada_depois": depois,
            "varredura_independente": varredura.stdout.strip(), "varredura_ok": varredura.returncode == 0}


def main() -> None:
    resultado = {"data": datetime.now().isoformat(timespec="seconds"),
                 "1_contradicao": contradicao(), "2_decaimento": decaimento(),
                 "3_remocao": remocao_completa()}
    # o próprio relatório não pode guardar o id removido, senão a varredura
    # seguinte o encontraria aqui — o titular aparece mascarado.
    texto = json.dumps(resultado, ensure_ascii=False, indent=2).replace(TITULAR, "<titular-de-teste>")
    destino = config.LOGS_DIR / "medicoes" / "demo_memoria.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    print(texto[:4000])
    print(f"\nlog: {destino.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
