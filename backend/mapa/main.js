document.addEventListener("DOMContentLoaded", async () => {
  const el = (id) => document.getElementById(id);

  const estado = {
    origem: { ...CONFIG.origemPadrao },
    destino: null,
    resultado: null,
    opcao: -1,
    sugestoes: [],
    marcadorOrigem: null,
    marcadorDestino: null,
    marcadoresEstacoes: new Map(),
  };

  // ---------- Mapa ----------
  const map = L.map("map", { zoomControl: false, preferCanvas: true }).setView(
    [estado.origem.lat, estado.origem.lng],
    CONFIG.mapa.zoomInicial,
  );
  L.control.zoom({ position: "bottomright" }).addTo(map);

  // Mapa do OpenStreetMap em modo padrão claro (sem chave de API)
  const urlMapa = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const creditoMapa =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  const bases = {
    Padrão: L.tileLayer(urlMapa, { attribution: creditoMapa, maxZoom: 19 }),
    Escuro: L.tileLayer(urlMapa, {
      attribution: creditoMapa,
      maxZoom: 19,
      className: "tiles-escuros",
    }),
  };
  bases["Padrão"].addTo(map);

  const camadaEstacoes = L.layerGroup().addTo(map);
  const camadaSemaforos = L.layerGroup().addTo(map);
  const camadaPontos = L.layerGroup().addTo(map);

  L.control
    .layers(
      bases,
      {
        Carregadores: camadaEstacoes,
        "Semáforos na rota": camadaSemaforos,
      },
      { position: "topright" },
    )
    .addTo(map);

  function iconePonto(classe, icone) {
    return L.divIcon({
      className: "ponto-wrap",
      html: `<div class="ponto ${classe}">${icone ? `<i class="fas ${icone}"></i>` : ""}</div>`,
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    });
  }

  function iconeEstacao(est, prev, destaque) {
    return L.divIcon({
      className: `custom-charger-icon ${destaque ? "pino-recomendado" : ""}`,
      html: `<div class="pino status-${prev.estado}"><i class="fas fa-bolt"></i></div><span class="pino-kw">${est.potenciaKw}</span>`,
      iconSize: [36, 46],
      iconAnchor: [18, 16],
    });
  }

  // ---------- Origem e destino ----------
  async function nomeDoLocal(lat, lng) {
    return RouteService.nomeDoLocal(lat, lng);
  }

  function definirOrigem(lat, lng, nome) {
    estado.origem = { lat, lng, nome: nome || "Ponto no mapa" };
    el("origemTxt").value = estado.origem.nome;

    if (!estado.marcadorOrigem) {
      estado.marcadorOrigem = L.marker([lat, lng], {
        icon: iconePonto("ponto-origem", ""),
        draggable: true,
        zIndexOffset: 500,
        title: "Saída (arraste para mudar)",
      }).addTo(camadaPontos);

      estado.marcadorOrigem.on("dragend", async () => {
        const p = estado.marcadorOrigem.getLatLng();
        definirOrigem(p.lat, p.lng, "Buscando endereço…");
        const nome = await nomeDoLocal(p.lat, p.lng);
        estado.origem.nome = nome;
        el("origemTxt").value = nome;
      });
    } else {
      estado.marcadorOrigem.setLatLng([lat, lng]);
    }

    limparResultado();
    atualizarLista();
  }

  function definirDestino(lat, lng, nome) {
    estado.destino = { lat, lng, nome: nome || "Ponto no mapa" };
    el("destinoTxt").value = estado.destino.nome;
    esconderSugestoes();

    if (!estado.marcadorDestino) {
      estado.marcadorDestino = L.marker([lat, lng], {
        icon: iconePonto("ponto-destino", "fa-flag-checkered"),
        draggable: true,
        zIndexOffset: 500,
        title: "Destino (arraste para mudar)",
      }).addTo(camadaPontos);

      estado.marcadorDestino.on("dragend", async () => {
        const p = estado.marcadorDestino.getLatLng();
        definirDestino(p.lat, p.lng, "Buscando endereço…");
        const nome = await nomeDoLocal(p.lat, p.lng);
        estado.destino.nome = nome;
        el("destinoTxt").value = nome;
      });
    } else {
      estado.marcadorDestino.setLatLng([lat, lng]);
    }

    limparResultado();
  }

  function removerDestino() {
    estado.destino = null;
    if (estado.marcadorDestino) {
      camadaPontos.removeLayer(estado.marcadorDestino);
      estado.marcadorDestino = null;
    }
    limparResultado();
  }

  function localizar(silencioso) {
    if (!navigator.geolocation) {
      if (!silencioso)
        UI.aviso("Seu navegador não permite acessar a localização.", "atencao");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        definirOrigem(latitude, longitude, "Minha localização");
        map.flyTo([latitude, longitude], 13);
      },
      () => {
        if (!silencioso)
          UI.aviso(
            "Não foi possível acessar a localização. Verifique a permissão do navegador.",
            "atencao",
          );
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  // ---------- Busca de destino ----------
  function esconderSugestoes() {
    el("sugestoes").hidden = true;
    el("sugestoes").innerHTML = "";
  }

  async function buscarDestino() {
    const texto = el("destinoTxt").value.trim();
    if (texto.length < 3) {
      UI.aviso("Digite pelo menos 3 letras para buscar o destino.", "atencao");
      return;
    }
    const botao = el("btnBuscar");
    botao.disabled = true;
    try {
      estado.sugestoes = await RouteService.buscarEndereco(
        texto,
        map.getBounds(),
      );
      if (!estado.sugestoes.length) {
        UI.aviso(
          "Nenhum local encontrado. Tente incluir a cidade no texto.",
          "atencao",
        );
        return;
      }
      el("sugestoes").innerHTML = estado.sugestoes
        .map(
          (s, i) =>
            `<li><button type="button" data-sugestao="${i}"><i class="fas fa-location-dot"></i>${Fmt.esc(s.nome)}</button></li>`,
        )
        .join("");
      el("sugestoes").hidden = false;
    } catch (err) {
      UI.aviso(
        "Não foi possível buscar o endereço agora. Tente de novo em instantes.",
        "erro",
      );
    } finally {
      botao.disabled = false;
    }
  }

  el("sugestoes").addEventListener("click", (ev) => {
    const botao = ev.target.closest("[data-sugestao]");
    if (!botao) return;
    const s = estado.sugestoes[Number(botao.dataset.sugestao)];
    definirDestino(s.lat, s.lng, s.nome);
    map.flyTo([s.lat, s.lng], 12);
  });

  el("btnBuscar").addEventListener("click", buscarDestino);
  el("destinoTxt").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      buscarDestino();
    }
  });
  el("destinoTxt").addEventListener("input", () => {
    if (estado.destino) removerDestino();
  });

  el("atalhos").innerHTML = CONFIG.destinosRapidos
    .map(
      (d, i) =>
        `<button type="button" class="chip" data-atalho="${i}">${Fmt.esc(d.nome)}</button>`,
    )
    .join("");
  el("atalhos").addEventListener("click", (ev) => {
    const botao = ev.target.closest("[data-atalho]");
    if (!botao) return;
    const d = CONFIG.destinosRapidos[Number(botao.dataset.atalho)];
    definirDestino(d.lat, d.lng, d.nome);
    map.flyTo([d.lat, d.lng], 11);
  });

  el("btnLocalizar").addEventListener("click", () => localizar(false));

  // Clique no mapa: escolher saída ou destino
  map.on("click", (ev) => {
    const { lat, lng } = ev.latlng;
    L.popup({ closeButton: false, className: "popup-escolha" })
      .setLatLng(ev.latlng)
      .setContent(
        `<div class="popup-escolha-corpo">
                <button type="button" data-acao="origem" data-lat="${lat}" data-lng="${lng}"><i class="fas fa-circle-dot"></i> Sair daqui</button>
                <button type="button" data-acao="destino" data-lat="${lat}" data-lng="${lng}"><i class="fas fa-flag-checkered"></i> Ir para cá</button>
            </div>`,
      )
      .openOn(map);
  });

  document.addEventListener("click", async (ev) => {
    const botao = ev.target.closest("[data-acao]");
    if (!botao) return;
    const { acao, lat, lng, id } = botao.dataset;

    if (acao === "origem" || acao === "destino") {
      map.closePopup();
      const la = Number(lat);
      const ln = Number(lng);
      if (acao === "origem") definirOrigem(la, ln, "Buscando endereço…");
      else definirDestino(la, ln, "Buscando endereço…");
      const nome = await nomeDoLocal(la, ln);
      if (acao === "origem") {
        estado.origem.nome = nome;
        el("origemTxt").value = nome;
      } else if (estado.destino) {
        estado.destino.nome = nome;
        el("destinoTxt").value = nome;
      }
    }

    if (acao === "ir-estacao") {
      const est = ChargerService.lista.find((e) => e.id === id);
      map.closePopup();
      if (est) {
        definirDestino(est.lat, est.lng, est.nome);
        abrirAba("viagem");
      }
    }
  });

  // ---------- Formulário ----------
  Object.entries(BatteryCalc.PERFIS).forEach(([id, p]) => {
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = `${p.nome} · ${p.capacidadeKwh} kWh`;
    el("veiculoSel").appendChild(opt);
  });
  el("veiculoSel").value = BatteryCalc.perfilId;
  el("veiculoSel").addEventListener("change", () => {
    BatteryCalc.definirPerfil(el("veiculoSel").value);
    limparResultado();
    renderizarEstacoes();
  });

  function atualizarSlider() {
    const v = Number(el("socInput").value);
    el("socOut").textContent = `${v}%`;
    el("socInput").style.setProperty("--pct", `${v}%`);
  }
  el("socInput").addEventListener("input", atualizarSlider);
  atualizarSlider();

  el("saidaInput").value = Fmt.paraInputLocal(new Date());
  el("btnAgora").addEventListener("click", () => {
    el("saidaInput").value = Fmt.paraInputLocal(new Date());
  });

  function lerSaida() {
    const data = new Date(el("saidaInput").value);
    const agora = new Date();
    return isNaN(data) || data < agora ? agora : data;
  }

  function definirCarregando(ativo) {
    const b = el("btnCalcularRota");
    b.disabled = ativo;
    b.innerHTML = ativo
      ? `<i class="fas fa-spinner fa-spin"></i> Calculando rota…`
      : `<i class="fas fa-route"></i> Planejar viagem`;
  }

  function mensagemDeErro(err) {
    if (err.name === "AbortError")
      return "O serviço de rotas demorou demais. Tente novamente.";
    if (/HTTP 429/.test(err.message))
      return "Muitas consultas seguidas. Aguarde alguns segundos e tente de novo.";
    return err.message || "Não foi possível planejar a viagem.";
  }

  el("formViagem").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!estado.destino) {
      UI.aviso(
        "Escolha um destino: busque um endereço, use um atalho ou clique no mapa.",
        "atencao",
      );
      el("destinoTxt").focus();
      return;
    }

    BatteryCalc.definirPerfil(el("veiculoSel").value);
    BatteryCalc.arCondicionado = el("arCond").checked;

    definirCarregando(true);
    try {
      const r = await TripPlanner.planejar({
        origem: estado.origem,
        destino: estado.destino,
        socAtual: Number(el("socInput").value),
        quando: lerSaida(),
        prioridade: document.querySelector("input[name='prioridade']:checked")
          .value,
      });
      estado.resultado = r;
      estado.opcao = r.opcoes.length ? 0 : -1;
      mostrarResultado();
      el("resultado").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      console.error(err);
      UI.aviso(mensagemDeErro(err), "erro");
    } finally {
      definirCarregando(false);
    }
  });

  // ---------- Resultado no mapa e no painel ----------
  function rotaAtiva() {
    const r = estado.resultado;
    if (!r) return null;
    return r.opcoes[estado.opcao] ? r.opcoes[estado.opcao].rota : r.direta;
  }

  function mostrarResultado() {
    const rota = rotaAtiva();
    RouteService.desenhar(map, rota.coordenadas);

    camadaSemaforos.clearLayers();
    rota.semaforos.pontos.forEach(([lat, lng]) => {
      L.circleMarker([lat, lng], {
        radius: 3,
        weight: 1,
        color: "#0d1420",
        fillColor: "#facc15",
        fillOpacity: 1,
        interactive: false,
      }).addTo(camadaSemaforos);
    });

    el("resultado").innerHTML = UI.resultadoHtml(
      estado.resultado,
      estado.opcao,
    );
    renderizarEstacoes();
  }

  function limparResultado() {
    if (!estado.resultado) return;
    estado.resultado = null;
    estado.opcao = -1;
    RouteService.limpar(map);
    camadaSemaforos.clearLayers();
    el("resultado").innerHTML = "";
    renderizarEstacoes();
  }

  el("resultado").addEventListener("click", (ev) => {
    const botao = ev.target.closest("[data-opcao]");
    if (botao) {
      estado.opcao = Number(botao.dataset.opcao);
      mostrarResultado();
      return;
    }
    const passo = ev.target.closest("li[data-lat]");
    if (passo)
      map.setView([Number(passo.dataset.lat), Number(passo.dataset.lng)], 17);
  });

  // ---------- Carregadores ----------
  function paradaAtiva() {
    const r = estado.resultado;
    return r && r.opcoes[estado.opcao] ? r.opcoes[estado.opcao] : null;
  }

  function estacoesFiltradas() {
    const soDisp = el("filterAvailable").checked;
    const soRapido = el("filterFastCharge").checked;
    const soCompat = el("filterCompat").checked;
    const agora = new Date();
    const destaque = paradaAtiva() ? paradaAtiva().est.id : null;

    return ChargerService.lista.filter((est) => {
      if (est.id === destaque) return true;
      if (soDisp && ChargerService.previsao(est, agora).estado !== "disponivel")
        return false;
      if (soRapido && est.potenciaKw < 50) return false;
      if (soCompat && !ChargerService.compativel(est)) return false;
      return true;
    });
  }

  let estacaoSelecionadaId = null;

  function calcularCentroVisivel(lat, lng, zoom) {
    const isEmbed =
      document.body.classList.contains("modo-embed") ||
      new URLSearchParams(window.location.search).get("embed") === "1";
    if (!isEmbed) return [lat, lng];

    const alturaMapa = map.getSize().y || 600;
    // O painel inferior cobre cerca de 52% da tela. Deslocamos o centro em ~20%
    // para baixo em pixels, fazendo o ponto ficar perfeitamente visível na metade superior da tela.
    const offsetPixels = Math.round(alturaMapa * 0.20);
    const pontoPixels = map.project([lat, lng], zoom).add([0, offsetPixels]);
    return map.unproject(pontoPixels, zoom);
  }

  function destacarEstacaoNoMapa(id, lat, lng) {
    const idStr = String(id);
    const est = ChargerService.lista.find((e) => String(e.id) === idStr);
    const marcador = estado.marcadoresEstacoes.get(idStr);

    // Remove classe de destaque dos demais marcadores
    estado.marcadoresEstacoes.forEach((m) => {
      const elPino = m.getElement();
      if (elPino) elPino.classList.remove("pino-selecionado");
    });

    if (marcador) {
      const elMarcador = marcador.getElement();
      if (elMarcador) {
        elMarcador.classList.add("pino-selecionado");
      }

      estacaoSelecionadaId = idStr;
      const destinoLat = lat || (est ? est.lat : marcador.getLatLng().lat);
      const destinoLng = lng || (est ? est.lng : marcador.getLatLng().lng);

      const zoomAlvo = Math.max(map.getZoom(), 16);
      const centroAjustado = calcularCentroVisivel(destinoLat, destinoLng, zoomAlvo);

      map.setView(centroAjustado, zoomAlvo, {
        animate: true,
      });
      marcador.openPopup();
    }
  }

  // Ouve comandos vindos da tela pai (mapa.html)
  window.addEventListener("message", (ev) => {
    if (!ev.data) return;
    if (ev.data.tipo === "SELECIONAR_POSTO") {
      destacarEstacaoNoMapa(ev.data.estacaoId, ev.data.lat, ev.data.lng);
    } else if (ev.data.tipo === "REDIMENSIONAR_MAPA") {
      map.invalidateSize();
    } else if (ev.data.tipo === "VOLTAR_MINHA_LOCALIZACAO") {
      const pos = estado.marcadorOrigem
        ? estado.marcadorOrigem.getLatLng()
        : estado.origem;
      if (pos) {
        const zoomAlvo = Math.max(map.getZoom(), 15);
        const centroAjustado = calcularCentroVisivel(pos.lat, pos.lng, zoomAlvo);
        map.flyTo(centroAjustado, zoomAlvo, {
          animate: true,
          duration: 0.8,
        });
      }
    }
  });

  function renderizarEstacoes() {
    camadaEstacoes.clearLayers();
    estado.marcadoresEstacoes.clear();

    const agora = new Date();
    const parada = paradaAtiva();

    estacoesFiltradas().forEach((est) => {
      const prev = ChargerService.previsao(est, agora);
      const marcador = L.marker([est.lat, est.lng], {
        icon: iconeEstacao(est, prev, parada && parada.est.id === est.id),
        title: est.nome,
        riseOnHover: true,
      })

        .addTo(camadaEstacoes);

      // 1º clique destaca o point do conector; 2º clique vai para os detalhes do posto
      marcador.on("click", (e) => {
        const idStr = String(est.id);
        if (estacaoSelecionadaId === idStr) {
          // Segundo clique no mesmo posto: redireciona para a tela de detalhes
          (window.parent || window).location.href =
            `/posto?estacao_id=${est.id}`;
        } else {
          // Primeiro clique: destaca o pino no mapa
          destacarEstacaoNoMapa(est.id, est.lat, est.lng);

          // Comunica à tela pai (mapa.html) para destacar o card da lista
          if (window.parent && window.parent !== window) {
            window.parent.postMessage(
              {
                tipo: "SELECAO_POSTO_MAPA",
                estacaoId: est.id,
              },
              "*",
            );
          }
        }
      });

      estado.marcadoresEstacoes.set(String(est.id), marcador);
    });

    atualizarLista();
  }

  function atualizarLista() {
    const agora = new Date();
    const rota = rotaAtiva();

    const itens = estacoesFiltradas().map((est) => {
      const noTracado = rota
        ? Geo.projetarNoTracado(est, rota.coordenadas, rota.acumulado)
        : null;
      return {
        est,
        prev: ChargerService.previsao(est, agora),
        compativel: ChargerService.compativel(est),
        distKm: Geo.haversine(estado.origem, est),
        naRota: noTracado !== null && noTracado.desvioKm <= 3,
        kmNaRota: noTracado ? noTracado.kmNaRota : 0,
      };
    });

    // Quem está na rota vem primeiro, na ordem do trajeto; o resto por proximidade
    itens.sort((a, b) => {
      if (a.naRota !== b.naRota) return a.naRota ? -1 : 1;
      return a.naRota ? a.kmNaRota - b.kmNaRota : a.distKm - b.distKm;
    });

    el("listaEstacoes").innerHTML = itens.length
      ? itens.map((i) => UI.itemEstacao(i)).join("")
      : `<li class="vazio">Nenhum carregador com esses filtros. Desmarque algum filtro para ver mais.</li>`;
    el("contagemEstacoes").textContent = itens.length;
  }

  el("listaEstacoes").addEventListener("click", (ev) => {
    const botao = ev.target.closest("[data-id]");
    if (!botao) return;
    const est = ChargerService.lista.find((e) => e.id === botao.dataset.id);
    const marcador = estado.marcadoresEstacoes.get(botao.dataset.id);
    if (!est || !marcador) return;
    map.flyTo([est.lat, est.lng], 14);
    map.once("moveend", () => marcador.openPopup());
  });

  ["filterAvailable", "filterFastCharge", "filterCompat"].forEach((id) =>
    el(id).addEventListener("change", renderizarEstacoes),
  );

  // ---------- Abas ----------
  function abrirAba(nome) {
    document
      .querySelectorAll("[data-aba]")
      .forEach((b) =>
        b.setAttribute("aria-selected", String(b.dataset.aba === nome)),
      );
    el("abaViagem").hidden = nome !== "viagem";
    el("abaCarregadores").hidden = nome !== "carregadores";
  }
  document
    .querySelectorAll("[data-aba]")
    .forEach((b) => b.addEventListener("click", () => abrirAba(b.dataset.aba)));

  // ---------- Início ----------
  document.addEventListener("click", (ev) => {
    if (!ev.target.closest(".campo-destino")) esconderSugestoes();
  });
  window.addEventListener("resize", () => map.invalidateSize());

  definirOrigem(estado.origem.lat, estado.origem.lng, estado.origem.nome);
  await ChargerService.carregar();
  renderizarEstacoes();

  // Centraliza o mapa de forma chumbada perto dos postos e da origem (na área visível superior)
  const centroInicial = calcularCentroVisivel(estado.origem.lat, estado.origem.lng, CONFIG.mapa.zoomInicial);
  map.setView(centroInicial, CONFIG.mapa.zoomInicial);

  // Garante que o Leaflet calcule o tamanho exato da tela e renderize todos os blocos (tiles) por completo
  function forcarCarregamentoCompleto() {
    map.invalidateSize();
  }
  forcarCarregamentoCompleto();
  setTimeout(forcarCarregamentoCompleto, 100);
  setTimeout(forcarCarregamentoCompleto, 350);
  setTimeout(forcarCarregamentoCompleto, 800);
});
