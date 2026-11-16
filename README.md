# Setores e empresas da B3: retorno, risco e múltiplos

[![Atualização diária](https://github.com/mlsantos92/setores-b3/actions/workflows/atualizar.yml/badge.svg)](https://github.com/mlsantos92/setores-b3/actions/workflows/atualizar.yml)
**[Ver painel ao vivo](https://mlsantos92.github.io/setores-b3/)** · atualizado em dias úteis às 08h30 e 19h15, com selo de situação.

Estudo de **282 empresas da B3**, divididas em large e mid caps e em small e micro caps, nos 11 setores da bolsa. Para cada empresa e cada setor: retorno em 5 anos, volatilidade, maior queda, Sharpe e múltiplos (P/L, P/VP, EV/EBITDA, dividend yield, ROE). Os múltiplos partem dos **resultados oficiais protocolados na CVM**, auditados ou revisados por auditor independente.

**Perguntas:** quais setores pagaram o risco que correram? As small caps renderam mais que as grandes? Onde os múltiplos estão acima ou abaixo da mediana do setor?

> Material de estudo. Nenhum resultado deste repositório é recomendação de compra ou de venda.

![Painel: retorno e risco por setor](docs/painel.png)

## Principais leituras (retrato de 13/11/2026, 5 anos)

- **Nenhum grupo bateu o CDI.** O CDI rendeu 12,8% ao ano no período. O índice de pesos iguais das large e mid caps rendeu 6,5% ao ano; o das small e micro caps, 0,3% ao ano. O Ibovespa, que pesa por valor de mercado, rendeu 10,6% ao ano.
- **Só três setores ficaram acima do CDI:** Financeiro (16,8% a.a.), Utilidade Pública (16,6% a.a.) e Comunicações (13,4% a.a.). Os dois primeiros também tiveram a menor volatilidade.
- **Os piores:** Saúde (−11,3% a.a.), Consumo Não Cíclico (−7,2% a.a.) e Consumo Cíclico (−7,0% a.a.). O Consumo Cíclico teve a maior volatilidade (35,4%).
- **Tamanho ajudou na maioria dos setores.** As large e mid caps renderam mais que as small e micro caps em 7 dos 11 setores. As exceções: Financeiro, Materiais Básicos, Consumo Cíclico e Tecnologia. Em quatro setores um dos grupos tem menos de 3 empresas elegíveis, então a comparação ali é frágil.
- **Small caps são mais baratas nos múltiplos, com motivo:** P/L mediano de 7,7 contra 9,5 das grandes e P/VP de 0,87 contra 1,38, com ROE menor (8,7% contra 12,9%).
- **Base auditada:** 189 das 192 empresas elegíveis têm os múltiplos calculados das demonstrações protocoladas na CVM. Das 192, 159 são auditadas por uma Big 4. Em 42 empresas o número oficial difere mais de 25% do Yahoo Finance; nas units o Yahoo chega a errar o P/L em várias vezes (BTG Pactual: 13 pela CVM, 86 no Yahoo).

Os números mudam a cada atualização; o painel traz sempre o retrato mais recente.

## Do universo ao painel

| Etapa | Empresas |
|---|---|
| Lista original (large e mid caps: 89; small e micro caps: 193) | 282 |
| Com preço na fonte, após ajustes de código | 251 |
| Fora dos agregados por dado suspeito (salto de preço de um dia) | 9 |
| Fora dos agregados por pouca liquidez | 50 |
| **Elegíveis: entram nos índices e nas medianas dos setores** | **192** |

As 31 empresas sem preço são as que saíram da bolsa (Neoenergia, Santos Brasil, Carrefour Brasil, Banco Pan, entre outras) e as que a fonte não cobre. A lista completa, com o motivo quando conhecido, está no fim do painel.

## Decisões de método

- **Uma ação por empresa.** Quando a lista traz ON, PN e unit, fica o código de maior volume financeiro mediano nos últimos 60 pregões.
- **Códigos que mudaram.** A lista original não é alterada. As trocas de código (ELET3 → AXIA3, CCRO3 → MOTV3, EMBR3 → EMBJ3, ODPV3 → SAUD3 e outras) e as saídas da bolsa ficam em [`data/raw/ajustes_tickers.json`](data/raw/ajustes_tickers.json).
- **Retorno total.** Os preços são ajustados por proventos, então o retorno inclui dividendos reinvestidos.
- **Índice do setor com pesos iguais**, rebalanceado todo dia, só com empresas elegíveis. Não é investível e difere dos índices setoriais da B3, que pesam por valor de mercado. Por isso o estudo mostra a empresa típica do setor, não a maior.
- **Elegíveis:** negócio em pelo menos 90% dos pregões dos últimos 12 meses e giro mediano de ao menos R$ 100 mil por dia.
- **Dado suspeito:** alta de mais de 100% ou queda de mais de 80% em um dia costuma ser grupamento ou troca de código que a fonte não ajustou. A empresa aparece na tabela com a marca e fica fora dos agregados.
- **Resultados oficiais e auditados.** P/L, P/VP, ROE e margem saem das demonstrações que a empresa protocola na CVM, as mesmas do portal de relações com investidores: DFP anual, auditada, e ITR trimestral, revisado pelo auditor independente. O lucro é o dos últimos 12 meses atribuído aos controladores (DFP + acumulado do ano − mesmo período do ano anterior); o patrimônio exclui minoritários.
- **Auditor de cada empresa**, com marca para as Big 4 (Deloitte, EY, KPMG e PwC) e aviso quando o relatório da última DFP tem ressalva.
- **Valor de mercado próprio:** ações informadas à CVM, fora a tesouraria, vezes o preço de cada classe. Em units, vale o preço das classes ou o da unit dividido pelas ações que ela representa.
- **Yahoo como conferência e reserva.** Diferença acima de 25% entre as fontes vira a marca “≠ Yahoo” e vale o número da CVM. Sem dado na CVM (BDRs, por exemplo), vale o Yahoo e o painel avisa. O EV/EBITDA vem do Yahoo.
- **Resultado atrasado:** empresa sem resultado protocolado há mais de 9 meses fica sem múltiplos.
- **Múltiplos por mediana**, não por média: um P/L de 130 não distorce o setor. P/L só existe para empresas com lucro; o painel conta quantas têm prejuízo.
- **Dividend yield calculado aqui:** proventos pagos em 12 meses ÷ preço atual. Acima de 30% é descartado.

## Limitações

- **Viés de sobrevivência.** A lista foi montada em 2026. Empresas que quebraram ou saíram da bolsa antes não entram, o que melhora o retorno histórico, sobretudo das small caps.
- **O que “auditado” cobre.** O estudo usa os números das demonstrações e o nome do auditor informado à CVM. Não lê o texto do parecer nem as notas explicativas, e o ITR tem revisão limitada, não auditoria completa.
- **Lucro contábil, sem ajustes.** O lucro de 12 meses inclui itens não recorrentes e operações descontinuadas, e fusões recentes (Bradsaúde, MBRF) misturam períodos de empresas diferentes. Os releases de RI costumam mostrar também um lucro ajustado, que não entra aqui.
- **Quantidade de ações sem escala.** A CVM não informa se o número está em unidades ou em milhares; a escala é decidida por comparação com o valor de mercado do Yahoo. Empresas com classes de ações de direitos econômicos diferentes ficam com o valor de mercado do Yahoo.
- **Preços de fonte única.** Cotações e proventos vêm do Yahoo Finance.
- **Setores pequenos.** Comunicações, Tecnologia e Outros têm poucas empresas elegíveis. Grupos com menos de 3 empresas ficam fora dos gráficos.
- **Feriados locais.** O calendário desconta feriados nacionais. Em feriado só da B3, o selo pode ficar amarelo por um dia.
- **Classificação dos setores** é a da lista original, sem revisão.

## Como funciona

| Etapa | Onde |
|---|---|
| Universo e ajustes de código | `data/raw/`, `src/setores_b3/universo.py` |
| Coleta de preços (Yahoo Finance) e do CDI (Banco Central) | `src/setores_b3/coleta.py` |
| Resultados oficiais, capital e auditor (CVM: DFP, ITR e FCA) | `src/setores_b3/cvm.py` |
| Retorno, volatilidade, maior queda, Sharpe, índice de pesos iguais | `src/setores_b3/metricas.py` |
| Múltiplos, conferência entre fontes e mediana do setor | `src/setores_b3/multiplos.py` |
| Escolha do código, elegibilidade e agregados | `src/setores_b3/estudo.py` |
| Calendário de pregões e selo de situação | `src/setores_b3/calendario.py`, `src/setores_b3/selo.py` |
| Painel estático | `docs/index.html`, que lê `docs/dados.json` |
| Atualização diária | `.github/workflows/atualizar.yml` |

Só os módulos de coleta falam com a rede. Os cálculos recebem tabelas prontas, o que permite testar tudo sem internet: são 40 testes com dados sintéticos (`pytest`), incluindo demonstrações fictícias no formato da CVM.

**Selo:** verde quando pelo menos 95% das large e mid caps têm preço do último pregão fechado, há fundamentos para 80% das elegíveis e os testes passam. Amarelo quando algum desses pontos falha. Vermelho quando a coleta ou os testes quebram.

## Como rodar

```bash
git clone https://github.com/mlsantos92/setores-b3
cd setores-b3
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

pytest -q                          # testes, sem internet
TESTES_OK=1 python scripts/atualizar.py   # coleta e gera docs/dados.json (uns 4 minutos)
python -m http.server -d docs 8000        # painel em http://localhost:8000
```

## Licença

MIT. Os dados pertencem às suas fontes.
