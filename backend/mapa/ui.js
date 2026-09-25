// Montagem dos blocos visuais (HTML) do painel e dos popups do mapa
const UI = {
  aviso(texto, tipo = "info") {
    const area = document.getElementById("avisos");
    const item = document.createElement("div");
    item.className = `aviso aviso-${tipo}`;
    item.textContent = texto;
    area.appendChild(item);
    setTimeout(() => item.remove(), 6000);
  },

  // Gráfico da carga da bateria ao longo do trajeto
  graficoBateria(pontos, kmTotal, { parada = null, esgota = false } = {}) {
    const W = 340,
      H = 140,
      ml = 40,
      mr = 14,
      mt = 24,
      mb = 24;
    const x = (km) => ml + (km / kmTotal) * (W - ml - mr);
    const y = (soc) =>
      mt + (1 - Math.min(100, Math.max(0, soc)) / 100) * (H - mt - mb);
    const reserva = CONFIG.bateria.reservaSoc;
    const ruim = esgota || pontos[pontos.length - 1].soc < reserva;

    const linha = pontos
      .map((p) => `${x(p.km).toFixed(1)},${y(p.soc).toFixed(1)}`)
      .join(" ");
    const chao = y(0).toFixed(1);
    const area = `${x(pontos[0].km).toFixed(1)},${chao} ${linha} ${x(pontos[pontos.length - 1].km).toFixed(1)},${chao}`;

    // Eixo vertical: 100%, 50% e a reserva (em vermelho) no lugar do 0%
    const grade =
      [0, 50, 100]
        .map(
          (v) =>
            `<line class="g-grade" x1="${ml}" x2="${W - mr}" y1="${y(v)}" y2="${y(v)}"/>`,
        )
        .join("") +
      [50, 100]
        .map(
          (v) =>
            `<text class="g-eixo" x="${ml - 6}" y="${y(v) + 3}" text-anchor="end">${v}%</text>`,
        )
        .join("") +
      `<text class="g-reserva-txt" x="${ml - 6}" y="${y(reserva) + 3}" text-anchor="end">${reserva}%</text>`;

    // Rótulos dos valores: o último, o primeiro e a saída da recarga têm prioridade;
    // um rótulo é omitido se o ponto estiver colado em outro já rotulado.
    const ordem = pontos
      .map((_, i) => i)
      .sort((a, b) => {
        const peso = (i) =>
          i === pontos.length - 1 ? 0 : i === 0 ? 1 : i === 2 ? 2 : 3;
        return peso(a) - peso(b);
      });
    const usados = [];
    const textos = {};
    ordem.forEach((i) => {
      const p = pontos[i];
      const px = x(p.km);
      const py = p.alerta ? y(0) + 11 : y(p.soc) + (p.abaixo ? 16 : -8);
      const pontoY = y(p.soc);
      if (
        usados.some(
          (u) => Math.abs(u[0] - px) < 30 && Math.abs(u[1] - pontoY) < 22,
        )
      )
        return;
      usados.push([px, pontoY]);
      textos[i] =
        `<text class="${p.alerta ? "g-alerta" : "g-valor"}" x="${px.toFixed(1)}" y="${py.toFixed(1)}" text-anchor="${p.ancora || "middle"}">${p.texto || Fmt.pct(p.soc)}</text>`;
    });
    const marcadores = pontos
      .map(
        (p, i) =>
          `<circle class="g-ponto" cx="${x(p.km).toFixed(1)}" cy="${y(p.soc).toFixed(1)}" r="4"/>${textos[i] || ""}`,
      )
      .join("");

    const px = parada === null ? 0 : x(parada);
    const marcaParada =
      parada === null
        ? ""
        : `
            <line class="g-parada" x1="${px}" x2="${px}" y1="${mt - 4}" y2="${H - mb}"/>
            <text class="g-recarga" x="${px}" y="${mt - 9}" text-anchor="${px < W / 2 ? "start" : "end"}">recarga aos ${Fmt.km(parada)}</text>`;

    return `<svg class="grafico ${ruim ? "ruim" : ""}" viewBox="0 0 ${W} ${H}" role="img"
                aria-label="Gráfico da carga da bateria ao longo do trajeto">
            ${grade}
            <line class="g-reserva" x1="${ml}" x2="${W - mr}" y1="${y(reserva)}" y2="${y(reserva)}"/>
            ${marcaParada}
            <polygon class="g-area" points="${area}"/>
            <polyline class="g-linha" points="${linha}"/>
            ${marcadores}
            <text class="g-eixo" x="${ml}" y="${H - 3}" text-anchor="start">0 km</text>
            <text class="g-eixo" x="${W - mr}" y="${H - 3}" text-anchor="end">${Fmt.km(kmTotal)}</text>
        </svg>`;
  },

  // Barra de tempo: quanto da viagem é direção, espera e recarga
  linhaDoTempo(trechos, inicio) {
    const ativos = trechos.filter((t) => t.min >= 0.5);
    const total = ativos.reduce((s, t) => s + t.min, 0) || 1;
    const chegada = new Date(inicio.getTime() + total * 60000);

    const barras = ativos
      .map(
        (t) =>
          `<span class="lt-${t.tipo}" style="flex:${t.min}" title="${t.rotulo}: ${Fmt.duracao(t.min)}"></span>`,
      )
      .join("");
    const legenda = ativos
      .map(
        (t) =>
          `<li><i class="lt-${t.tipo}"></i>${t.rotulo} <b>${Fmt.duracao(t.min)}</b></li>`,
      )
      .join("");

    return `<div class="tempo">
            <div class="tempo-horas"><span>Saída <b>${Fmt.hora(inicio)}</b></span><span>Chegada <b>${Fmt.hora(chegada)}</b></span></div>
            <div class="tempo-barra">${barras}</div>
            <ul class="tempo-legenda">${legenda}</ul>
        </div>`;
  },

  resultadoHtml(r, idx) {
    const opcao = r.opcoes[idx] || null;
    const rota = opcao ? opcao.rota : r.direta;
    const a = r.analise;
    const reserva = CONFIG.bateria.reservaSoc;
    const totalMin = opcao ? opcao.totalMin : r.direta.tempoMin;

    // Veredito
    let v;
    if (a.suportaViagem) {
      v = {
        tipo: "ok",
        icone: "fa-circle-check",
        titulo: "Bateria suficiente",
        texto: `Você chega com ${Fmt.pct(a.socRestante)}, acima da reserva de ${reserva}%.`,
      };
    } else if (opcao) {
      const semParar =
        a.socRestante <= 0
          ? "a bateria acabaria antes do destino"
          : `você chegaria com só ${Fmt.pct(a.socRestante)}`;
      v = {
        tipo: "parada",
        icone: "fa-charging-station",
        titulo: "Recarga necessária",
        texto: `Sem parar, ${semParar}. Sugestão: recarregar em ${Fmt.esc(opcao.est.nome)}.`,
      };
    } else {
      v = {
        tipo: "erro",
        icone: "fa-triangle-exclamation",
        titulo: "A bateria não chega ao destino",
        texto: Fmt.esc(r.diagnostico),
      };
    }

    // Pontos do gráfico
    let pontos;
    let extra = {};
    if (opcao) {
      const km1 = rota.pernas[0].distanciaKm;
      pontos = [
        { km: 0, soc: r.socAtual, ancora: "start" },
        { km: km1, soc: opcao.sim.socChegada, ancora: "end", abaixo: true },
        { km: km1, soc: opcao.sim.socSaida, ancora: "start" },
        { km: rota.distanciaKm, soc: opcao.sim.socDestino, ancora: "end" },
      ];
      extra = { parada: km1 };
    } else if (a.socRestante < 0) {
      const kmZero =
        (rota.distanciaKm * r.socAtual) / (r.socAtual - a.socRestante);
      pontos = [
        { km: 0, soc: r.socAtual, ancora: "start" },
        {
          km: kmZero,
          soc: 0,
          ancora: "end",
          texto: `bateria acaba aos ${Fmt.km(kmZero)}`,
          alerta: true,
        },
      ];
      extra = { esgota: true };
    } else {
      pontos = [
        { km: 0, soc: r.socAtual, ancora: "start" },
        { km: rota.distanciaKm, soc: a.socRestante, ancora: "end" },
      ];
    }

    // Linha do tempo
    const trechos = opcao
      ? [
          {
            tipo: "dirigir",
            rotulo: "Até o carregador",
            min: rota.pernas[0].tempoMin,
          },
          { tipo: "espera", rotulo: "Fila", min: opcao.sim.esperaMin },
          { tipo: "carga", rotulo: "Recarga", min: opcao.sim.cargaMin },
          {
            tipo: "dirigir",
            rotulo: "Até o destino",
            min: rota.pernas[1].tempoMin,
          },
        ]
      : [{ tipo: "dirigir", rotulo: "Dirigindo", min: rota.tempoMin }];

    // Cartões de números
    const transito =
      rota.atrasoTransitoMin >= 1
        ? `+${Fmt.duracao(rota.atrasoTransitoMin)} no horário`
        : "sem atraso";
    const semaforoTxt = `${rota.semaforos.estimado ? "≈" : ""}${rota.semaforos.quantidade}`;
    const stats = [
      {
        icone: "fa-road",
        rotulo: "Distância",
        valor: Fmt.km(rota.distanciaKm),
        sub: `média ${Math.round(rota.velocidadeMediaKmh)} km/h`,
      },
      {
        icone: "fa-clock",
        rotulo: "Tempo total",
        valor: Fmt.duracao(totalMin),
        sub: opcao ? "com parada" : "sem paradas",
      },
      {
        icone: "fa-bolt",
        rotulo: "Consumo",
        valor: `${rota.consumo.kwh.toFixed(1).replace(".", ",")} kWh`,
        sub: `${Fmt.pct(rota.consumo.socPercent)} da bateria`,
      },
      {
        icone: "fa-traffic-light",
        rotulo: "Semáforos",
        valor: semaforoTxt,
        sub: `+${Fmt.duracao(rota.atrasoSemaforosMin)} parado${rota.semaforos.estimado ? " (estimado)" : ""}`,
      },
      {
        icone: "fa-car-side",
        rotulo: "Trânsito",
        valor: rota.ctx.rotulo,
        sub: transito,
      },
      opcao
        ? {
            icone: "fa-wallet",
            rotulo: "Custo da recarga",
            valor: Fmt.dinheiro(opcao.sim.custo),
            sub: `${opcao.sim.kwhCarregados.toFixed(1).replace(".", ",")} kWh`,
          }
        : {
            icone: "fa-gauge-high",
            rotulo: "Velocidade média",
            valor: `${Math.round(rota.velocidadeMediaKmh)} km/h`,
            sub: "no trajeto",
          },
    ]
      .map(
        (s) =>
          `<div class="stat"><i class="fas ${s.icone}"></i><span>${s.rotulo}</span><b>${s.valor}</b><small>${s.sub}</small></div>`,
      )
      .join("");

    // Opções de recarga
    const selo = r.prioridade === "custo" ? "Mais barato" : "Mais rápido";
    const opcoesHtml = r.opcoes.length
      ? `
            <h3 class="secao">Onde recarregar</h3>
            <div class="opcoes">${r.opcoes
              .map(
                (o, i) => `
                <button type="button" class="opcao ${i === idx ? "ativa" : ""}" data-opcao="${i}" aria-pressed="${i === idx}">
                    <span class="opcao-topo"><b>${Fmt.esc(o.est.nome)}</b>${i === 0 ? `<em class="selo">${selo}</em>` : ""}</span>
                    <span class="opcao-meta">${o.sim.potenciaKw} kW ${o.sim.corrente} · desvio de ${Fmt.km(o.desvioKm)} · ${o.sim.esperaMin ? `fila de ~${Fmt.duracao(o.sim.esperaMin)}` : "sem fila prevista"}</span>
                    <span class="opcao-nums">
                        <span>${Fmt.pct(o.sim.socChegada)} → ${Fmt.pct(o.sim.socSaida)} em ${Fmt.duracao(o.sim.cargaMin)}</span>
                        <b>${Fmt.dinheiro(o.sim.custo)}</b>
                    </span>
                </button>`,
              )
              .join("")}
            </div>`
      : "";

    // Passo a passo
    const passos = rota.pernas.flatMap((p) => p.passos);
    const passosHtml = `
            <details class="passos">
                <summary>Passo a passo (${passos.length} instruções)</summary>
                <ol>${passos
                  .map(
                    (p) => `
                    <li data-lat="${p.ponto[0]}" data-lng="${p.ponto[1]}">
                        <i class="fas ${p.icone}"></i>
                        <span>${p.texto}${p.via ? `<small>${Fmt.esc(p.via)}</small>` : ""}</span>
                        <em>${Fmt.metros(p.distanciaM)}</em>
                    </li>`,
                  )
                  .join("")}
                </ol>
            </details>`;

    return `
            <div class="veredito veredito-${v.tipo}">
                <i class="fas ${v.icone}"></i>
                <div><b>${v.titulo}</b><p>${v.texto}</p></div>
            </div>
            <h3 class="secao">Bateria no caminho</h3>
            ${this.graficoBateria(pontos, rota.distanciaKm, extra)}
            <h3 class="secao">Tempo de viagem</h3>
            ${this.linhaDoTempo(trechos, r.quando)}
            <div class="stats">${stats}</div>
            ${opcoesHtml}
            ${passosHtml}
            <p class="nota">Rota conforme o mapeamento viário (sentido das vias, conversões e acessos permitidos).
            O tempo considera o padrão de trânsito do horário de saída e os semáforos mapeados, sem trânsito ao vivo.</p>`;
  },

  itemEstacao({ est, prev, compativel, distKm, naRota }) {
    return `<li><button type="button" class="estacao ${compativel ? "" : "incompativel"}" data-id="${Fmt.esc(est.id)}">
            <span class="estacao-status ${prev.estado}" aria-hidden="true"></span>
            <span class="estacao-corpo">
                <b>${Fmt.esc(est.nome)}</b>
                <small style="color: #64748b;"><i class="fas fa-location-dot" style="color: #f97316; font-size: 10px;"></i> ${Fmt.esc(est.endereco || "Endereço da API")}</small>
            </span>
            <span class="estacao-lado">${Fmt.km(distKm)}${naRota ? `<em class="selo">na rota</em>` : ""}</span>
        </button></li>`;
  },
};
