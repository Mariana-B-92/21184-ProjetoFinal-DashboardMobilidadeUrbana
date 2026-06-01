window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, latlng) {
            return L.circleMarker(latlng, {
                radius: 4,
                color: '#0a9a4a',
                weight: 1,
                fillColor: '#0a9a4a',
                fillOpacity: 0.7
            });
        },
        function1: function(feature, latlng, context) {
            const h = context.hideout;
            let v = feature.properties[h.prop];
            if (v === null || v === undefined) v = h.vmin;
            let t = (h.vmax > h.vmin) ? (v - h.vmin) / (h.vmax - h.vmin) : 0.5;
            if (h.inverter) t = 1 - t;
            t = Math.max(0, Math.min(1, t));
            const s = h.stops;
            const n = s.length - 1;
            const seg = Math.min(Math.floor(t * n), n - 1);
            const u = t * n - seg;
            const a = s[seg],
                b = s[seg + 1];
            const cor = 'rgb(' + Math.round(a[0] + (b[0] - a[0]) * u) + ',' +
                Math.round(a[1] + (b[1] - a[1]) * u) + ',' +
                Math.round(a[2] + (b[2] - a[2]) * u) + ')';
            return L.circleMarker(latlng, {
                radius: 8,
                color: '#ffffff',
                weight: 2,
                fillColor: cor,
                fillOpacity: 1.0
            });
        }
    }
});