// Trânsito por horário e semáforos ao longo da rota.
// Os semáforos vêm do mapeamento do OpenStreetMap (highway=traffic_signals).
// O trânsito usa um padrão típico da Grande São Paulo por dia/hora, NÃO é trânsito ao vivo.
// Para dados em tempo real, troque contexto() por uma API de tráfego (HERE, TomTom, Google Routes).
const TrafficService = {
    SEGUNDOS_POR_SEMAFORO: 15,
    _cache: new Map(),

    contexto(data = new Date()) {
        const dia = data.getDay(); // 0 = domingo
        const h = data.getHours() + data.getMinutes() / 60;
        const diaUtil = dia >= 1 && dia <= 5;

        if (diaUtil && h >= 6.5 && h < 9.5) {
            return { fator: 1.55, nivel: "intenso", rotulo: "Pico da manhã" };
        }
        if (diaUtil && h >= 16.5 && h < 20.5) {
            return { fator: 1.75, nivel: "intenso", rotulo: "Pico da tarde" };
        }
        if (diaUtil && h >= 9.5 && h < 16.5) {
            return { fator: 1.2, nivel: "moderado", rotulo: "Movimento moderado" };
        }
        if (!diaUtil && h >= 10 && h < 20) {
            return { fator: 1.15, nivel: "moderado", rotulo: "Movimento de fim de semana" };
        }
        return { fator: 1, nivel: "livre", rotulo: "Trânsito livre" };
    },

    // Vias rápidas sentem menos o congestionamento do que vias urbanas
    _fatorPorVelocidade(v, fator) {
        if (fator === 1) return 1;
        if (v >= 80) return 1 + (fator - 1) * 0.25;
        if (v >= 60) return 1 + (fator - 1) * 0.7;
        return fator;
    },

    // segmentos: [{ d: km, v: km/h }]. Retorna tempo livre e tempo com trânsito, em minutos.
    tempoSegmentos(segmentos, ctx) {
        let livre = 0;
        let real = 0;
        for (const s of segmentos) {
            const horas = s.d / s.v;
            livre += horas;
            real += horas * this._fatorPorVelocidade(s.v, ctx.fator);
        }
        return { livreMin: livre * 60, comTransitoMin: real * 60 };
    },

    atrasoSemaforosMin(quantidade, ctx) {
        const filas = ctx.nivel === "intenso" ? 1.4 : 1;
        return (quantidade * this.SEGUNDOS_POR_SEMAFORO * filas) / 60;
    },

    // Usado quando a consulta ao Overpass falha: estima pela densidade de vias urbanas
    _estimarQuantidade(segmentos) {
        let n = 0;
        for (const s of segmentos) {
            if (s.v <= 50) n += s.d * 1.6;
            else if (s.v <= 70) n += s.d * 0.6;
        }
        return Math.round(n);
    },

    async buscarSemaforos(coordenadas, segmentos) {
        const meio = coordenadas[Math.floor(coordenadas.length / 2)];
        const chave = `${coordenadas.length}|${coordenadas[0]}|${meio}|${coordenadas[coordenadas.length - 1]}`;
        if (this._cache.has(chave)) return this._cache.get(chave);

        try {
            // A consulta aceita poucos pontos, então simplificamos o traçado
            // e aumentamos a tolerância até caber em ~400 pontos.
            let tolKm = 0.015;
            let pontos = Geo.simplificar(coordenadas, tolKm);
            while (pontos.length > 400 && tolKm < 0.08) {
                tolKm *= 1.6;
                pontos = Geo.simplificar(coordenadas, tolKm);
            }

            const raioM = Math.round(tolKm * 1000 + 20);
            const lista = pontos.map(p => `${p[0].toFixed(5)},${p[1].toFixed(5)}`).join(",");
            const consulta = `[out:json][timeout:20];node["highway"="traffic_signals"](around:${raioM},${lista});out skel;`;

            const dados = await Http.json(CONFIG.servicos.overpass, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: "data=" + encodeURIComponent(consulta)
            }, 25000);

            const achados = (dados.elements || []).map(e => [e.lat, e.lon]);
            const resultado = { pontos: achados, quantidade: achados.length, estimado: false };
            this._cache.set(chave, resultado);
            return resultado;
        } catch (err) {
            console.warn("Semáforos: consulta indisponível, usando estimativa.", err);
            return { pontos: [], quantidade: this._estimarQuantidade(segmentos), estimado: true };
        }
    }
};
