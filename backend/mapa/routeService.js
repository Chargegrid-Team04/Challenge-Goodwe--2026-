// Rotas reais (OSRM sobre dados do OpenStreetMap), busca de endereços (Nominatim) e desenho no mapa.
// As rotas respeitam o sentido das vias, conversões proibidas e acessos permitidos do mapeamento.
// Observação: o servidor público do OSRM é para demonstração. Em produção, use instância própria ou um provedor pago.
const RouteService = {
    camadas: [],

    // pontos: [{lat, lng}, ...]. Com 3 pontos, o trajeto passa pelo do meio (parada de recarga).
    async obterRota(pontos) {
        const trajeto = pontos.map(p => `${p.lng},${p.lat}`).join(";");
        const url = `${CONFIG.servicos.osrm}/route/v1/driving/${trajeto}` +
            `?overview=full&geometries=geojson&steps=true&annotations=distance,duration`;

        const dados = await Http.json(url, {}, CONFIG.rota.timeoutMs);
        if (dados.code !== "Ok" || !dados.routes || !dados.routes.length) {
            throw new Error("Não foi possível traçar uma rota entre esses pontos.");
        }

        const rota = dados.routes[0];
        const pernas = rota.legs.map((leg, i) => this._lerPerna(leg, i === rota.legs.length - 1));

        return {
            coordenadas: rota.geometry.coordinates.map(([lng, lat]) => [lat, lng]),
            distanciaKm: rota.distance / 1000,
            pernas
        };
    },

    _lerPerna(leg, ultima) {
        const a = leg.annotation;
        const segmentos = [];
        a.distance.forEach((metros, i) => {
            const seg = a.duration[i];
            if (metros > 0 && seg > 0) {
                const kmh = (metros / seg) * 3.6;
                segmentos.push({ d: metros / 1000, v: Math.min(Math.max(kmh, 5), CONFIG.rota.limiteMaxKmh) });
            }
        });

        return {
            distanciaKm: leg.distance / 1000,
            segmentos,
            passos: leg.steps.map(s => this._lerPasso(s, ultima)).filter(Boolean)
        };
    },

    _lerPasso(passo, ultimaPerna) {
        const { type, modifier, exit, location } = passo.maneuver;
        if (type === "new name" || type === "notification") return null;

        const lados = {
            left: "à esquerda",
            right: "à direita",
            "slight left": "levemente à esquerda",
            "slight right": "levemente à direita",
            "sharp left": "fechando à esquerda",
            "sharp right": "fechando à direita",
            straight: "em frente",
            uturn: "fazendo o retorno"
        };
        const lado = lados[modifier] || "";

        let texto;
        switch (type) {
            case "depart": texto = "Siga pela via"; break;
            case "arrive": texto = ultimaPerna ? "Você chegou ao destino" : "Chegada ao carregador"; break;
            case "turn": texto = lado ? `Vire ${lado}` : "Vire"; break;
            case "end of road": texto = lado ? `No fim da via, vire ${lado}` : "No fim da via, vire"; break;
            case "fork": texto = lado ? `Mantenha-se ${lado}` : "Mantenha-se na via"; break;
            case "merge": texto = "Entre na via"; break;
            case "on ramp": texto = lado ? `Pegue a entrada ${lado}` : "Pegue a entrada"; break;
            case "off ramp": texto = lado ? `Pegue a saída ${lado}` : "Pegue a saída"; break;
            case "roundabout":
            case "rotary": texto = exit ? `Na rotatória, pegue a ${exit}ª saída` : "Entre na rotatória"; break;
            case "roundabout turn": texto = lado ? `Na rotatória, vire ${lado}` : "Na rotatória, vire"; break;
            default: texto = lado ? `Continue ${lado}` : "Continue em frente";
        }

        let icone = "fa-arrow-up";
        if (type === "arrive") icone = ultimaPerna ? "fa-flag-checkered" : "fa-charging-station";
        else if (modifier === "uturn") icone = "fa-rotate-left";
        else if (/left/.test(modifier || "")) icone = "fa-arrow-left";
        else if (/right/.test(modifier || "")) icone = "fa-arrow-right";
        else if (type === "roundabout" || type === "rotary") icone = "fa-rotate";

        return {
            texto,
            via: passo.name || "",
            distanciaM: passo.distance,
            icone,
            ponto: [location[1], location[0]]
        };
    },

    desenhar(map, coordenadas) {
        this.limpar(map);
        const contorno = L.polyline(coordenadas, {
            color: "#0b1220", weight: 9, opacity: 0.85, lineCap: "round", lineJoin: "round", interactive: false
        }).addTo(map);
        const linha = L.polyline(coordenadas, {
            color: "#f97316", weight: 5, opacity: 1, lineCap: "round", lineJoin: "round", interactive: false
        }).addTo(map);

        this.camadas = [contorno, linha];
        map.fitBounds(linha.getBounds(), { padding: [50, 50] });
    },

    limpar(map) {
        this.camadas.forEach(c => map.removeLayer(c));
        this.camadas = [];
    },

    // Nominatim pede no máximo 1 consulta por segundo e proíbe autocompletar a cada tecla.
    // Por isso a busca só roda quando a pessoa confirma (Enter ou botão).
    async buscarEndereco(texto, limitesMapa) {
        let url = `${CONFIG.servicos.nominatim}/search?format=jsonv2&limit=5&countrycodes=br` +
            `&accept-language=pt-BR&q=${encodeURIComponent(texto)}`;
        if (limitesMapa) url += `&viewbox=${limitesMapa.toBBoxString()}`;

        const dados = await Http.json(url, {}, 12000);
        return dados.map(d => ({
            nome: d.display_name.split(",").slice(0, 3).join(",").trim(),
            completo: d.display_name,
            lat: parseFloat(d.lat),
            lng: parseFloat(d.lon)
        }));
    },

    async nomeDoLocal(lat, lng) {
        try {
            const url = `${CONFIG.servicos.nominatim}/reverse?format=jsonv2&zoom=17&accept-language=pt-BR&lat=${lat}&lon=${lng}`;
            const d = await Http.json(url, {}, 8000);
            const a = d.address || {};
            const via = a.road || a.pedestrian || a.name || "";
            const bairro = a.suburb || a.neighbourhood || "";
            const cidade = a.city || a.town || a.village || a.municipality || "";
            const partes = [via, bairro, cidade].filter(Boolean);
            if (partes.length) return partes.join(", ");
        } catch (err) {
            console.warn("Endereço não encontrado para o ponto.", err);
        }
        return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    }
};
