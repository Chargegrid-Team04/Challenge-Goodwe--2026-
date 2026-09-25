// Planejamento da viagem: combina rota real, trânsito, semáforos, bateria e carregadores
const TripPlanner = {
    async planejar({ origem, destino, socAtual, quando, prioridade }) {
        const direta = await this.avaliarRota([origem, destino], quando);
        const analise = BatteryCalc.validarAutonomia(direta.consumo.kwh, socAtual);

        let opcoes = [];
        let diagnostico = "";
        if (!analise.suportaViagem) {
            ({ opcoes, diagnostico } = await this.buscarParadas({ origem, destino, socAtual, quando, prioridade, direta }));
        }

        return { direta, analise, opcoes, diagnostico, socAtual, quando, prioridade };
    },

    // Calcula tempo (com trânsito e semáforos) e consumo de uma rota e de cada perna dela
    async avaliarRota(pontos, quando) {
        const rota = await RouteService.obterRota(pontos);
        const ctx = TrafficService.contexto(quando);
        const todos = rota.pernas.flatMap(p => p.segmentos);
        const semaforos = await TrafficService.buscarSemaforos(rota.coordenadas, todos);
        const atrasoSemaforosMin = TrafficService.atrasoSemaforosMin(semaforos.quantidade, ctx);

        const pernas = rota.pernas.map(p => {
            const t = TrafficService.tempoSegmentos(p.segmentos, ctx);
            const parteSemaforos = atrasoSemaforosMin * (p.distanciaKm / rota.distanciaKm);
            return {
                ...p,
                tempoLivreMin: t.livreMin,
                tempoMin: t.comTransitoMin + parteSemaforos,
                consumoKwh: BatteryCalc.consumoKwh(p.segmentos)
            };
        });

        const soma = campo => pernas.reduce((s, p) => s + p[campo], 0);
        const tempoMin = soma("tempoMin");
        const tempoLivreMin = soma("tempoLivreMin");
        const kwh = soma("consumoKwh");

        return {
            coordenadas: rota.coordenadas,
            acumulado: Geo.acumulado(rota.coordenadas),
            pernas,
            distanciaKm: rota.distanciaKm,
            tempoMin,
            atrasoTransitoMin: tempoMin - tempoLivreMin - atrasoSemaforosMin,
            atrasoSemaforosMin,
            velocidadeMediaKmh: rota.distanciaKm / (tempoMin / 60),
            ctx,
            semaforos,
            consumo: {
                kwh,
                socPercent: BatteryCalc.kwhParaSoc(kwh),
                kwhPorKm: kwh / rota.distanciaKm
            }
        };
    },

    // Simula parar em um carregador: chega com quanto, recarrega até quanto, em quanto tempo e por quanto.
    simularParada({ est, kwhAte, kwhResto, socAtual, quando, tempoAteMin }) {
        const { reservaSoc, margemPlanejamento, tetoRecargaRapida, tetoRecargaLenta } = CONFIG.bateria;
        const chegada = new Date(quando.getTime() + tempoAteMin * 60000);

        const modo = BatteryCalc.modoDeCarga(est);
        if (!modo) return { viavel: false, motivo: "plug incompatível com o veículo" };

        const prev = ChargerService.previsao(est, chegada);
        if (prev.estado === "manutencao") return { viavel: false, motivo: "carregador em manutenção" };
        if (prev.estado === "fechado") return { viavel: false, motivo: "carregador fechado no horário previsto" };

        const socChegada = socAtual - BatteryCalc.kwhParaSoc(kwhAte);
        if (socChegada < reservaSoc) return { viavel: false, motivo: "a bateria não alcança o carregador" };

        const socNecessario = BatteryCalc.kwhParaSoc(kwhResto) + reservaSoc + margemPlanejamento;
        const teto = modo.corrente === "DC" ? tetoRecargaRapida : tetoRecargaLenta;
        if (socNecessario > teto) return { viavel: false, motivo: "seriam necessárias duas ou mais paradas" };

        const socSaida = socChegada >= socNecessario
            ? socChegada
            : Math.min(teto, Math.ceil(socNecessario / 5) * 5);
        const kwhCarregados = ((socSaida - socChegada) / 100) * BatteryCalc.perfil.capacidadeKwh;

        return {
            viavel: true,
            socChegada,
            socSaida,
            socDestino: socSaida - BatteryCalc.kwhParaSoc(kwhResto),
            cargaMin: BatteryCalc.tempoRecargaMin(socChegada, socSaida, modo.potenciaKw, modo.corrente),
            esperaMin: prev.esperaMin,
            vagasPrevistas: prev.vagasLivres,
            kwhCarregados,
            custo: kwhCarregados * est.precoKwh,
            potenciaKw: modo.potenciaKw,
            corrente: modo.corrente,
            chegada
        };
    },

    _comparar(prioridade) {
        return prioridade === "custo"
            ? (a, b) => a.sim.custo - b.sim.custo || a.totalMin - b.totalMin
            : (a, b) => a.totalMin - b.totalMin;
    },

    async buscarParadas({ origem, destino, socAtual, quando, prioridade, direta }) {
        const coords = direta.coordenadas;
        const kmTotal = direta.distanciaKm;
        const kwhKm = direta.consumo.kwhPorKm;
        const minPorKm = direta.tempoMin / kmTotal;
        const autonomia = BatteryCalc.autonomiaKm(socAtual, kwhKm);

        // 1) Pré-seleção rápida: carregadores perto da rota e ao alcance da bateria
        const candidatos = ChargerService.lista
            .map(est => ({ est, ...Geo.projetarNoTracado(est, coords, direta.acumulado) }))
            .filter(c => c.desvioKm <= CONFIG.rota.corredorKm &&
                c.kmNaRota + c.desvioKm * 1.3 <= autonomia * 1.05);

        if (!candidatos.length) {
            return {
                opcoes: [],
                diagnostico: "Não há carregador no trajeto ao alcance da bateria atual. Tente sair com mais carga."
            };
        }

        // 2) Estimativa por distância, só para escolher quem merece rota real
        const previas = candidatos.map(c => {
            const km1 = c.kmNaRota + c.desvioKm * 1.3;
            const km2 = kmTotal - c.kmNaRota + c.desvioKm * 1.3;
            const sim = this.simularParada({
                est: c.est,
                kwhAte: km1 * kwhKm,
                kwhResto: km2 * kwhKm,
                socAtual,
                quando,
                tempoAteMin: km1 * minPorKm
            });
            const totalMin = (km1 + km2) * minPorKm + (sim.viavel ? sim.esperaMin + sim.cargaMin : 0);
            return { ...c, sim, totalMin };
        });

        const viaveis = previas
            .filter(p => p.sim.viavel)
            .sort(this._comparar(prioridade))
            .slice(0, CONFIG.rota.maxCandidatos);

        if (!viaveis.length) {
            const motivos = [...new Set(previas.map(p => p.sim.motivo))].slice(0, 2).join("; ");
            return { opcoes: [], diagnostico: `Nenhum carregador serve para este trajeto (${motivos}).` };
        }

        // 3) Rota real (origem > carregador > destino) para os melhores candidatos
        const opcoes = [];
        for (const c of viaveis) {
            try {
                const rota = await this.avaliarRota(
                    [origem, { lat: c.est.lat, lng: c.est.lng }, destino],
                    quando
                );
                const [ate, resto] = rota.pernas;
                const sim = this.simularParada({
                    est: c.est,
                    kwhAte: ate.consumoKwh,
                    kwhResto: resto.consumoKwh,
                    socAtual,
                    quando,
                    tempoAteMin: ate.tempoMin
                });
                if (!sim.viavel) continue;

                opcoes.push({
                    est: c.est,
                    rota,
                    sim,
                    desvioKm: Math.max(0, rota.distanciaKm - direta.distanciaKm),
                    totalMin: rota.tempoMin + sim.esperaMin + sim.cargaMin
                });
            } catch (err) {
                console.warn(`Rota via ${c.est.nome} indisponível.`, err);
            }
        }

        opcoes.sort(this._comparar(prioridade));
        return {
            opcoes,
            diagnostico: opcoes.length ? "" : "Não foi possível calcular rota até os carregadores próximos. Tente novamente."
        };
    }
};
