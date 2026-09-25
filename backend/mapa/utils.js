// Funções auxiliares compartilhadas: geometria, requisições e formatação

const Geo = {
    RAIO_TERRA_KM: 6371,

    _ll(p) {
        return Array.isArray(p) ? p : [p.lat, p.lng];
    },

    // Distância em linha reta entre dois pontos (km). Aceita {lat,lng} ou [lat,lng]
    haversine(a, b) {
        const [la1, lo1] = this._ll(a);
        const [la2, lo2] = this._ll(b);
        const rad = Math.PI / 180;
        const dLat = (la2 - la1) * rad;
        const dLng = (lo2 - lo1) * rad;
        const h = Math.sin(dLat / 2) ** 2 +
            Math.cos(la1 * rad) * Math.cos(la2 * rad) * Math.sin(dLng / 2) ** 2;
        return 2 * this.RAIO_TERRA_KM * Math.asin(Math.sqrt(h));
    },

    // Converte [lat,lng] para km em um plano local centrado em "ref"
    _plano(p, ref) {
        const k = Math.PI / 180;
        return [(p[1] - ref[1]) * Math.cos(ref[0] * k) * 111.32, (p[0] - ref[0]) * 110.57];
    },

    // Menor distância (km) entre o ponto p e o segmento a-b, e a posição t (0..1) do ponto mais próximo
    _distSegmento(p, a, b) {
        const A = this._plano(a, p);
        const B = this._plano(b, p);
        const dx = B[0] - A[0];
        const dy = B[1] - A[1];
        const len2 = dx * dx + dy * dy;
        let t = len2 ? -(A[0] * dx + A[1] * dy) / len2 : 0;
        t = Math.max(0, Math.min(1, t));
        return { dist: Math.hypot(A[0] + t * dx, A[1] + t * dy), t };
    },

    // Distância acumulada (km) ao longo do traçado, ponto a ponto
    acumulado(coords) {
        const ac = [0];
        for (let i = 1; i < coords.length; i++) {
            ac.push(ac[i - 1] + this.haversine(coords[i - 1], coords[i]));
        }
        return ac;
    },

    // Projeta um ponto no traçado: quão longe ele fica da rota e em que km da rota ele "cai"
    projetarNoTracado(ponto, coords, acumulado) {
        const p = this._ll(ponto);
        let melhor = { desvioKm: Infinity, kmNaRota: 0 };
        for (let i = 1; i < coords.length; i++) {
            const { dist, t } = this._distSegmento(p, coords[i - 1], coords[i]);
            if (dist < melhor.desvioKm) {
                melhor = {
                    desvioKm: dist,
                    kmNaRota: acumulado[i - 1] + t * (acumulado[i] - acumulado[i - 1])
                };
            }
        }
        return melhor;
    },

    // Douglas-Peucker (versão iterativa). tolKm = tolerância em km
    simplificar(coords, tolKm) {
        if (coords.length < 3) return coords.slice();
        const manter = new Uint8Array(coords.length);
        manter[0] = manter[coords.length - 1] = 1;
        const pilha = [[0, coords.length - 1]];

        while (pilha.length) {
            const [ini, fim] = pilha.pop();
            let maior = 0;
            let idx = -1;
            for (let i = ini + 1; i < fim; i++) {
                const { dist } = this._distSegmento(coords[i], coords[ini], coords[fim]);
                if (dist > maior) { maior = dist; idx = i; }
            }
            if (idx !== -1 && maior > tolKm) {
                manter[idx] = 1;
                pilha.push([ini, idx], [idx, fim]);
            }
        }
        return coords.filter((_, i) => manter[i]);
    }
};

const Http = {
    async json(url, opcoes = {}, timeoutMs = 20000) {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), timeoutMs);
        try {
            const resp = await fetch(url, { ...opcoes, signal: ctrl.signal });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            return await resp.json();
        } finally {
            clearTimeout(timer);
        }
    }
};

const Fmt = {
    esc(texto) {
        const mapa = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
        return String(texto ?? "").replace(/[&<>"']/g, c => mapa[c]);
    },

    duracao(min) {
        const m = Math.max(0, Math.round(min));
        if (m < 60) return `${m} min`;
        const h = Math.floor(m / 60);
        const r = m % 60;
        return r ? `${h} h ${String(r).padStart(2, "0")} min` : `${h} h`;
    },

    km(v) {
        return `${v.toFixed(v < 10 ? 1 : 0).replace(".", ",")} km`;
    },

    metros(m) {
        return m < 1000 ? `${Math.max(10, Math.round(m / 10) * 10)} m` : Fmt.km(m / 1000);
    },

    dinheiro(v) {
        return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    },

    hora(data) {
        return data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    },

    pct(v) {
        return `${Math.round(v)}%`;
    },

    // Formato aceito pelo <input type="datetime-local">
    paraInputLocal(d) {
        const p = n => String(n).padStart(2, "0");
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
    }
};
