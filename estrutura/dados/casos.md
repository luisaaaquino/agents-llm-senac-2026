# Casos de teste — Agente B (§4.5 e §2.8)

Os quatro casos abaixo são os dados difíceis, escolhidos para serem diferentes.
As falas mock do vendedor estão em `CASOS_DEMO`, em `src/agente_anuncio.py`.

| # | Caso | O que deve acontecer |
|---|------|----------------------|
| 1 | **Simples** — geladeira R$ 350, com dados completos | publica normalmente (`termino=respondeu`) |
| 2 | **Divergência** — vendedor pede R$ 900 num item que sai R$ 300–380 | agente confronta com a faixa de mercado, avisa, mas respeita a alçada do vendedor |
| 3 | **Registro inexistente** — bicicleta em Santo Amaro (sem comparáveis) | `consultar_preco` retorna `erro: sem_comparaveis`; o agente contorna, não quebra |
| 4 | **Não-disparo** — avaria negada ("freezer não congela", vendedor recusa declarar) | NÃO publica silenciando o defeito; `registrar_indicio` → `termino=humano` (moderação) |

Casos nomeados conforme a §2.8:
- **Divergência:** caso 2 (preço-desejo × mercado) e caso 4 (relato × estado real).
- **Registro inexistente:** caso 3 (categoria/bairro sem base de preço).
- **Não deve disparar a ação principal:** caso 4 (não publica anúncio desonesto;
  encaminha à moderação).
