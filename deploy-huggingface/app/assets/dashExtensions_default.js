window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, latlng, context) {
            const h = (context && context.hideout) ? context.hideout : {};
            let cor, raio, op, peso;
            if (h.categorico || !h.prop) {
                cor = h.cor_fixa || '#0a9a4a';
                raio = 6;
                op = 0.9;
                peso = 1.5;
                if (h.esbatido) { raio = 4; peso = 1; }
            } else {
                let v = feature.properties[h.prop];
                if (v === null || v === undefined) v = h.vmin;
                let t = (h.vmax > h.vmin) ? (v - h.vmin) / (h.vmax - h.vmin) : 0.5;
                if (h.inverter) t = 1 - t;
                t = Math.max(0, Math.min(1, t));
                const s = h.stops;
                const idx = Math.min(Math.floor(t * s.length), s.length - 1);
                const c = s[idx];
                cor = 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
                raio = 8;
                op = 1.0;
                peso = 2;
            }
            const _m = L.circleMarker(latlng, {
                radius: raio,
                color: '#ffffff',
                weight: peso,
                fillColor: cor,
                fillOpacity: op,
                interactive: !h.esbatido,
                pane: h.esbatido ? 'p-contexto' : 'p-gira'
            });
            try { (window._giraLayers = window._giraLayers || {})[feature.properties.id_estacao] = _m; } catch (e) {}
            return _m;
        },
        function1: function(feature, latlng, context) {
            const h = context.hideout;
            let cor, raio, op, peso;
            if (h.categorico) {
                cor = h.cor_fixa;
                raio = 6;
                op = 0.9;
                peso = 1.5;
                if (h.esbatido) { raio = 4; peso = 1; }
                else if (h.destaque) { raio = 8; op = 1.0; peso = 2; }
            } else {
                let v = feature.properties[h.prop];
                if (v === null || v === undefined) v = h.vmin;
                let t = (h.vmax > h.vmin) ? (v - h.vmin) / (h.vmax - h.vmin) : 0.5;
                if (h.inverter) t = 1 - t;
                t = Math.max(0, Math.min(1, t));
                const s = h.stops;
                const idx = Math.min(Math.floor(t * s.length), s.length - 1);
                const c = s[idx];
                cor = 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
                raio = 8;
                op = 1.0;
                peso = 2;
            }
            const _m = L.circleMarker(latlng, {
                radius: raio,
                color: '#ffffff',
                weight: peso,
                fillColor: cor,
                fillOpacity: op,
                interactive: !h.esbatido,
                pane: h.esbatido ? 'p-contexto' : 'p-metro'
            });
            try { (window._metroLayers = window._metroLayers || {})[feature.properties.id_metro] = _m; } catch (e) {}
            return _m;
        },
        function2: function(feature, layer) {
            const p = feature.properties || {};
            if (p.nome_estacao) layer.bindTooltip(p.nome_estacao, { direction: 'top' });
            const pct = (p.taxa_media_disponibilidade == null) ? '–' :
                Math.round(p.taxa_media_disponibilidade * 100) + '%';
            layer.bindPopup(
                '<div class="popup-mapa">' +
                '<div class="popup-tipo">Estação GIRA</div>' +
                '<div class="popup-nome">' + (p.nome_estacao || 'Estação') + '</div>' +
                '<div class="popup-linha"><span>Disponibilidade média</span><b>' + pct + '</b></div>' +
                '</div>');
            layer.on('popupclose', function() {
                if (window._abrindoPopup) return;
                const c = window.dash_clientside;
                if (c && c.set_props) {
                    c.set_props('sel-gira', { data: null });
                    c.set_props('sel-metro', { data: null });
                    c.set_props('sel-gira-nome', { value: null });
                    c.set_props('sel-metro-nome', { value: null });
                }
            });
        },
        function3: function(feature, layer) {
            const p = feature.properties || {};
            if (p.nome_metro) layer.bindTooltip(p.nome_metro, { direction: 'top' });
            const iic = (p.iic == null) ? '–' : p.iic.toFixed(2).replace('.', ',');
            layer.bindPopup(
                '<div class="popup-mapa">' +
                '<div class="popup-tipo">Estação de metro</div>' +
                '<div class="popup-nome">' + (p.nome_metro || 'Estação') + '</div>' +
                '<div class="popup-linha"><span>IIC</span><b>' + iic + '</b></div>' +
                '</div>');
            layer.on('popupclose', function() {
                if (window._abrindoPopup) return;
                const c = window.dash_clientside;
                if (c && c.set_props) {
                    c.set_props('sel-gira', { data: null });
                    c.set_props('sel-metro', { data: null });
                    c.set_props('sel-gira-nome', { value: null });
                    c.set_props('sel-metro-nome', { value: null });
                }
            });
        }
    }
});