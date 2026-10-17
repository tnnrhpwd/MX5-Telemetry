/* Mimic harness: renders the car app in a browser at 800x480.
 *
 * Two jobs. First, turn the tokens extracted from Palette.java into CSS custom properties,
 * so the colours here are the app's colours and not a second copy of them. Second, build
 * the shell and the nine screens as DOM, mirroring the Java view code's structure.
 *
 * The parts that mirror Java deliberately keep the Java shape and names (panel, grid,
 * stat, bar, wash, pageGlow) so that reading one next to the other is easy. Where the
 * layout here and the layout in Ui.java could disagree, the Java is right and this is the
 * thing to fix.
 *
 * URL parameters, for driving it from Playwright without any clicking:
 *   ?screen=rpm&scheme=ocean&mode=light&narrow=1&offline=1
 */
(function () {
  'use strict';

  var T = window.MX5_TOKENS;
  if (!T) {
    document.body.textContent = 'tokens.js missing: run extract_tokens.py first.';
    return;
  }

  // ---------------------------------------------------------------- colour maths
  // Mirrors Palette.mix / lift / sink / alpha exactly, in sRGB with integer rounding,
  // because a mismatch here would make the harness subtly wrong rather than obviously so.

  function comps(v) {
    return { a: (v >>> 24) & 255, r: (v >>> 16) & 255, g: (v >>> 8) & 255, b: v & 255 };
  }

  function pack(a, r, g, b) {
    return (((a & 255) << 24) | ((r & 255) << 16) | ((g & 255) << 8) | (b & 255)) >>> 0;
  }

  function mix(c1, c2, t) {
    var x = comps(c1), y = comps(c2), u = 1 - t;
    return pack(Math.round(x.a * u + y.a * t), Math.round(x.r * u + y.r * t),
                Math.round(x.g * u + y.g * t), Math.round(x.b * u + y.b * t));
  }

  var WHITE = 0xFFFFFFFF, BLACK = 0xFF000000;

  function lift(c, t) { return mix(c, WHITE, t); }
  function sink(c, t) { return mix(c, BLACK, t); }
  function withAlpha(c, a) { var x = comps(c); return pack(Math.round(255 * a), x.r, x.g, x.b); }

  function css(c, alphaOverride) {
    var x = comps(c);
    var a = alphaOverride === undefined ? x.a / 255 : alphaOverride;
    return 'rgba(' + x.r + ', ' + x.g + ', ' + x.b + ', ' + a.toFixed(3) + ')';
  }

  function hexToInt(h) { return parseInt(h, 16) >>> 0; }

  // ---------------------------------------------------------------------- palette

  function palette(schemeId, dark) {
    var s = null;
    for (var i = 0; i < T.schemes.length; i++) {
      if (T.schemes[i].id === schemeId) { s = T.schemes[i]; }
    }
    if (!s) { s = T.schemes[0]; }

    var amt = T.fractions.seedAmount;
    var a = hexToInt(s.a), b = hexToInt(s.b);
    var accent = dark ? lift(a, amt) : sink(a, amt);
    var primary = dark ? lift(b, amt) : sink(b, amt);

    var base = T.modes[dark ? 'dark' : 'light'];
    var mode = dark ? 0 : 1;                   // index into the two-value fractions

    var page = hexToInt(base.page);
    var panel = hexToInt(base.panel);

    return {
      id: s.id, name: s.name, dark: dark,
      page: page,
      pageGlow: mix(page, accent, T.fractions.pageGlow[mode]),
      panel: panel,
      panelStroke: hexToInt(base.panelStroke),
      panelHead: mix(panel, accent, T.fractions.panelHead[mode]),
      tile: hexToInt(base.tile),
      hairline: hexToInt(base.hairline),
      text: hexToInt(base.text),
      textDim: hexToInt(base.textDim),
      track: hexToInt(base.track),
      accent: accent,
      primary: primary,
      alert: hexToInt(T.fixed.alert),
      good: hexToInt(T.fixed.good),
      bad: hexToInt(T.fixed.bad),
      warn: hexToInt(T.fixed.warn),
      washAccent: withAlpha(accent, T.fractions.wash[mode]),
      washGood: withAlpha(hexToInt(T.fixed.good), T.fractions.wash[mode]),
      washBad: withAlpha(hexToInt(T.fixed.bad), T.fractions.wash[mode]),
      washWarn: withAlpha(hexToInt(T.fixed.warn), T.fractions.wash[mode])
    };
  }

  function applyTheme(el, p) {
    var vars = {
      '--page': css(p.page),
      '--page-glow': css(p.pageGlow),
      '--panel': css(p.panel),
      '--panel-head': css(p.panelHead),
      '--panel-accent': css(p.accent),
      '--tile': css(p.tile),
      '--hairline': css(p.hairline),
      '--text': css(p.text),
      '--text-dim': css(p.textDim),
      '--track': css(p.track),
      '--accent': css(p.accent),
      '--primary': css(p.primary),
      '--good': css(p.good),
      '--bad': css(p.bad),
      '--warn': css(p.warn),
      '--wash-accent': css(p.washAccent),
      '--wash-good': css(p.washGood),
      '--wash-bad': css(p.washBad),
      '--wash-warn': css(p.washWarn),
      '--type-display': T.type.TYPE_DISPLAY + 'px',
      '--type-title': T.type.TYPE_TITLE + 'px',
      '--type-value': T.type.TYPE_VALUE + 'px',
      '--type-body': T.type.TYPE_BODY + 'px',
      '--type-label': T.type.TYPE_LABEL + 'px',
      '--type-eyebrow': T.type.TYPE_EYEBROW + 'px',
      '--s1': T.space.S1 + 'px',
      '--s2': T.space.S2 + 'px',
      '--s3': T.space.S3 + 'px',
      '--s4': T.space.S4 + 'px',
      '--s5': T.space.S5 + 'px'
    };
    Object.keys(vars).forEach(function (k) { el.style.setProperty(k, vars[k]); });
  }

  // ------------------------------------------------------------------- dom helpers

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined && text !== null) { n.textContent = text; }
    return n;
  }

  function tile(cap, val, unit, cls, fill) {
    var t = el('div', 'tile');
    t.appendChild(el('div', 'caption', cap));
    var row = el('div', 'value-row');
    row.appendChild(el('div', 'value' + (cls ? ' ' + cls : ''), val));
    if (unit) { row.appendChild(el('div', 'unit', unit)); }
    t.appendChild(row);
    if (fill) { /* grid rows handle stretching */ }
    return t;
  }

  function tileRow(tiles, fill) {
    var r = el('div', 'row' + (fill ? ' fill' : ''));
    tiles.forEach(function (t) { r.appendChild(t); });
    return r;
  }

  function barBlock(label, pct, text) {
    var b = el('div', 'bar-block');
    var head = el('div', 'bar-head');
    head.appendChild(el('span', null, label));
    head.appendChild(el('span', 'val', text));
    b.appendChild(head);
    var track = el('div', 'bar-track');
    var fill = el('div', 'bar-fill');
    fill.style.width = Math.max(0, Math.min(100, pct)) + '%';
    track.appendChild(fill);
    b.appendChild(track);
    return b;
  }

  function panel(title, eyebrow, accentVar) {
    var p = el('div', 'panel');
    var head = el('div', 'panel-head');
    var eb = el('div', 'panel-eyebrow', eyebrow);
    var tt = el('div', 'panel-title', title);
    if (accentVar && accentVar !== 'accent') { tt.style.color = 'var(--' + accentVar + ')'; }
    head.appendChild(eb);
    head.appendChild(tt);
    p.appendChild(head);
    var body = el('div', 'panel-body');
    p.appendChild(body);
    p.body = body;
    return p;
  }

  function sliderBlock(label, value, min, max, colour) {
    var b = el('div', 'slider-block');
    var head = el('div', 'slider-head');
    head.appendChild(el('span', null, label));
    var v = el('span', 'val', value);
    v.style.color = 'var(--' + (colour || 'accent') + ')';
    head.appendChild(v);
    b.appendChild(head);

    var track = el('div', 'slider-track');
    var knob = el('div', 'slider-knob');
    knob.style.left = ((value - min) / (max - min) * 100) + '%';
    knob.style.background = 'var(--' + (colour || 'accent') + ')';
    track.appendChild(knob);
    b.appendChild(track);
    return b;
  }

  function pillRow(label, on) {
    var r = el('div', 'pill-row');
    r.appendChild(el('span', null, label));
    r.appendChild(el('span', 'switch ' + (on ? 'on' : 'off'), on ? 'ON' : 'OFF'));
    return r;
  }

  function chips(names, selected) {
    var c = el('div', 'chips');
    names.forEach(function (n, i) {
      c.appendChild(el('div', 'chip' + (i === selected ? ' on' : ''), n));
    });
    return c;
  }

  function sectionLabel(text, gap) {
    return el('div', 'section-label' + (gap ? ' gap' : ''), text);
  }

  // -------------------------------------------------------------------- gauges

  /** 270 degrees from 135, same geometry as GaugeView.java. */
  function gaugeSvg(rpm, shift, redline, max) {
    var size = 232, cx = size / 2, cy = size / 2;
    var r = size * 0.44;
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    // Sized by CSS, not by attributes, so the dial fills its column rather than
    // floating in the middle of it.
    svg.setAttribute('viewBox', '0 0 ' + size + ' ' + size);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

    function polar(angleDeg, radius) {
      var rad = angleDeg * Math.PI / 180;
      return [cx + Math.cos(rad) * radius, cy + Math.sin(rad) * radius];
    }

    function arc(from, to, width, colour, cap) {
      var p1 = polar(from, r), p2 = polar(to, r);
      var large = (to - from) > 180 ? 1 : 0;
      var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', 'M ' + p1[0] + ' ' + p1[1] +
        ' A ' + r + ' ' + r + ' 0 ' + large + ' 1 ' + p2[0] + ' ' + p2[1]);
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', colour);
      path.setAttribute('stroke-width', width);
      path.setAttribute('stroke-linecap', cap || 'round');
      svg.appendChild(path);
    }

    // track, then the filled portion, then the shift and redline marks
    arc(135, 405, 9, 'var(--track)');
    var frac = Math.max(0, Math.min(1, rpm / max));
    if (frac > 0.001) { arc(135, 135 + 270 * frac, 9, 'var(--accent)'); }

    var shiftFrac = shift / max, redFrac = redline / max;
    arc(135 + 270 * shiftFrac, 135 + 270 * shiftFrac + 0.8, 9, 'var(--warn)', 'butt');
    arc(135 + 270 * redFrac, 405, 9, 'var(--bad)');

    // graduations
    for (var v = 0; v <= max; v += 500) {
      var major = (v % 1000 === 0);
      var a = 135 + 270 * (v / max);
      var p1 = polar(a, size * 0.345), p2 = polar(a, size * (major ? 0.295 : 0.32));
      var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', p1[0]); line.setAttribute('y1', p1[1]);
      line.setAttribute('x2', p2[0]); line.setAttribute('y2', p2[1]);
      line.setAttribute('stroke', major ? 'var(--text-dim)' : 'var(--track)');
      line.setAttribute('stroke-width', major ? 1.6 : 1);
      svg.appendChild(line);
    }

    // needle, stopped short of the graduations
    var na = 135 + 270 * frac;
    var hub = polar(na, size * 0.30);
    var needle = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    needle.setAttribute('x1', cx); needle.setAttribute('y1', cy);
    needle.setAttribute('x2', hub[0]); needle.setAttribute('y2', hub[1]);
    needle.setAttribute('stroke', frac >= shiftFrac ? 'var(--bad)' : 'var(--accent)');
    needle.setAttribute('stroke-width', size * 0.02);
    needle.setAttribute('stroke-linecap', 'round');
    svg.appendChild(needle);

    var dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    dot.setAttribute('cx', cx); dot.setAttribute('cy', cy);
    dot.setAttribute('r', size * 0.045);
    dot.setAttribute('fill', 'var(--accent)');
    svg.appendChild(dot);

    function text(y, content, sizePx, colour, weight) {
      var t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      t.setAttribute('x', cx); t.setAttribute('y', y);
      t.setAttribute('text-anchor', 'middle');
      t.setAttribute('fill', colour);
      t.setAttribute('font-size', sizePx);
      t.setAttribute('font-weight', weight || 600);
      t.setAttribute('font-family', 'Segoe UI, Roboto, sans-serif');
      t.textContent = content;
      svg.appendChild(t);
    }

    text(cy + size * 0.315, String(Math.round(rpm)), size * 0.22, 'var(--accent)', 700);
    text(cy + size * 0.44, 'shift ' + shift + '  redline ' + redline, size * 0.05,
         'var(--text-dim)', 600);
    text(cy - size * 0.10, 'RPM', size * 0.055, 'var(--text-dim)', 600);

    return svg;
  }

  function gforceSvg(gLat, gLong, peak) {
    var size = 232, cx = size / 2, cy = size / 2, range = 1.2, outer = size * 0.38;
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + size + ' ' + size);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

    function circle(radius, colour, width, dash, fill) {
      var c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      c.setAttribute('cx', cx); c.setAttribute('cy', cy); c.setAttribute('r', radius);
      c.setAttribute('fill', fill || 'none');
      c.setAttribute('stroke', colour);
      c.setAttribute('stroke-width', width);
      if (dash) { c.setAttribute('stroke-dasharray', dash); }
      svg.appendChild(c);
      return c;
    }

    function line(x1, y1, x2, y2, colour, width, opacity) {
      var l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      l.setAttribute('x1', x1); l.setAttribute('y1', y1);
      l.setAttribute('x2', x2); l.setAttribute('y2', y2);
      l.setAttribute('stroke', colour);
      l.setAttribute('stroke-width', width);
      if (opacity !== undefined) { l.setAttribute('opacity', opacity); }
      svg.appendChild(l);
    }

    function label(x, y, text, colour) {
      var t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      t.setAttribute('x', x); t.setAttribute('y', y);
      t.setAttribute('text-anchor', 'middle');
      t.setAttribute('fill', colour);
      t.setAttribute('font-size', size * 0.05);
      t.setAttribute('font-weight', 700);
      t.setAttribute('letter-spacing', '0.08em');
      t.setAttribute('font-family', 'Segoe UI, Roboto, sans-serif');
      t.textContent = text;
      svg.appendChild(t);
    }

    // A pad behind the rings. Without it the dial was thin grey circles adrift in a large
    // empty square, which read as an unfinished panel rather than an instrument.
    circle(outer, 'none', 0, null, 'var(--tile)');

    circle(outer * (0.4 / range), 'var(--track)', 1.5, '3 3');
    circle(outer * (0.8 / range), 'var(--track)', 1.5, '3 3');
    circle(outer, 'var(--hairline)', 2);

    // The axes, then the labels that make them mean something.
    line(cx - outer, cy, cx + outer, cy, 'var(--hairline)', 1);
    line(cx, cy - outer, cx, cy + outer, 'var(--hairline)', 1);
    label(cx, cy - outer - 10, 'ACCEL', 'var(--text-dim)');
    label(cx, cy + outer + 20, 'BRAKE', 'var(--text-dim)');
    label(cx - outer - 16, cy + 5, 'L', 'var(--text-dim)');
    label(cx + outer + 16, cy + 5, 'R', 'var(--text-dim)');

    var px = cx + (gLat / range) * outer;
    var py = cy - (gLong / range) * outer;

    // The vector from rest to the current load, so the direction is legible and not just
    // the position of a dot.
    line(cx, cy, px, py, 'var(--accent)', 2, 0.5);

    var d = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    d.setAttribute('cx', px); d.setAttribute('cy', py);
    d.setAttribute('r', size * 0.055);
    d.setAttribute('fill', 'var(--accent)');
    svg.appendChild(d);

    // The peak magnitude, as a ring from rest rather than around the dot: it is a distance
    // from zero g, and centring it on the current point would read as a tolerance band.
    if (peak > 0) {
      var pk = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      pk.setAttribute('cx', cx); pk.setAttribute('cy', cy);
      pk.setAttribute('r', outer * (peak / range));
      pk.setAttribute('fill', 'none');
      pk.setAttribute('stroke', 'var(--warn)');
      pk.setAttribute('stroke-width', 1.5);
      pk.setAttribute('stroke-dasharray', '4 3');
      svg.appendChild(pk);
    }

    return svg;
  }

  function gaugeWrap(svg) {
    var w = el('div', 'gauge-wrap');
    w.appendChild(svg);
    return w;
  }

  /**
   * The readout column beside a dial: full-width tiles, all the same shape, sharing the
   * height evenly. The old layout mixed a 2-up row with a full-width one, which made the
   * odd row look like a mistake rather than a hierarchy.
   */
  function statColumn(stats) {
    var c = el('div', 'stat-column');
    stats.forEach(function (s) {
      c.appendChild(tile(s[0], s[1], s[2], s[3]));
    });
    return c;
  }

  // -------------------------------------------------------------------- screens

  var OFF = 'waiting';

  var SCREENS = [
    {
      id: 'overview', rail: 'Overview', title: 'Overview', eyebrow: 'Telemetry',
      accent: 'accent',
      build: function (o) {
        var p = panel('Overview', 'TELEMETRY', 'accent');
        p.body.appendChild(tileRow([
          tile('SPEED', o ? OFF : '38', o ? 'mph' : 'mph', o ? 'dim' : null),
          tile('RPM', o ? OFF : '3120', '', o ? 'dim' : null),
          tile('GEAR', o ? OFF : '4', o ? '' : 'est', o ? 'dim' : null),
          tile('COOLANT', o ? OFF : '188', o ? '\u00b0F' : '\u00b0F', o ? 'dim' : null)
        ], true));
        p.body.appendChild(tileRow([
          tile('FUEL', o ? OFF : '62', o ? '%' : '%', o ? 'dim' : null),
          tile('RANGE', o ? OFF : '218', o ? 'mi' : 'mi', o ? 'dim' : null),
          tile('BATTERY', o ? OFF : '14.2', o ? 'V' : 'V', o ? 'dim' : null),
          tile('AVG', o ? OFF : '27.4', o ? 'mpg' : 'mpg', o ? 'dim' : null)
        ], true));
        var bars = el('div', 'bars-strip');
        bars.appendChild(barBlock('Fuel level', o ? 0 : 62, o ? '\u2013' : '62%'));
        bars.appendChild(barBlock('Throttle', o ? 0 : 24, o ? '\u2013' : '24%'));
        bars.appendChild(barBlock('Brake', 0, '0%'));
        p.body.appendChild(bars);
        return p;
      }
    },
    {
      id: 'rpm', rail: 'RPM', title: 'RPM / Speed', eyebrow: 'Tachometer',
      accent: 'accent',
      build: function (o) {
        var p = panel('RPM / Speed', 'TACHOMETER', 'accent');
        var r = el('div', 'row fill');
        r.appendChild(gaugeWrap(gaugeSvg(o ? 0 : 3120, 6500, 7200, 8000)));
        r.appendChild(statColumn([
          ['SPEED', o ? OFF : '38', 'mph', o ? 'dim' : null],
          ['GEAR', o ? OFF : '4', 'est', o ? 'dim' : null],
          ['SHIFT AT', '6500', 'rpm', 'dim'],
          ['REDLINE', '7200', 'rpm', 'dim']
        ]));
        p.body.appendChild(r);
        var side2 = r.querySelector('.stat-column');
        if (side2) { side2.appendChild(barBlock('Throttle', o ? 0 : 24, o ? '\u2013' : '24%')); }
        return p;
      }
    },
    {
      id: 'tpms', rail: 'TPMS', title: 'Tire Pressure', eyebrow: 'Wheels',
      accent: 'accent',
      build: function (o) {
        var p = panel('Tire Pressure', o ? 'TPMS \u00b7 NO DATA' : 'TPMS \u00b7 LINKED', 'accent');
        p.body.appendChild(tileRow([
          tile('FRONT LEFT', o ? OFF : '31.5', 'psi', o ? 'dim' : 'ok'),
          tile('FRONT RIGHT', o ? OFF : '31.0', 'psi', o ? 'dim' : 'ok')
        ], true));
        p.body.appendChild(tileRow([
          tile('REAR LEFT', o ? OFF : '30.5', 'psi', o ? 'dim' : 'ok'),
          tile('REAR RIGHT', o ? OFF : '29.0', 'psi', o ? 'dim' : 'caution')
        ], true));
        p.body.appendChild(tileRow([
          tile('FL TEMP', o ? OFF : '96', '\u00b0F', o ? 'dim' : null),
          tile('FR TEMP', o ? OFF : '95', '\u00b0F', o ? 'dim' : null)
        ], true));
        p.body.appendChild(tileRow([
          tile('RL TEMP', o ? OFF : '92', '\u00b0F', o ? 'dim' : null),
          tile('RR TEMP', o ? OFF : '98', '\u00b0F', o ? 'dim' : null)
        ], true));
        return p;
      }
    },
    {
      id: 'engine', rail: 'Engine', title: 'Engine', eyebrow: 'Powertrain',
      accent: 'primary',
      build: function (o) {
        var p = panel('Engine', 'POWERTRAIN', 'primary');
        p.body.appendChild(tileRow([
          tile('COOLANT', o ? OFF : '188', '\u00b0F', o ? 'dim' : 'ok'),
          tile('INTAKE', o ? OFF : '97', '\u00b0F', o ? 'dim' : null),
          tile('AMBIENT', o ? OFF : '61', '\u00b0F', o ? 'dim' : null),
          tile('OIL', o ? OFF : 'OK', '', o ? 'dim' : 'ok')
        ], true));
        p.body.appendChild(tileRow([
          tile('MAF', o ? OFF : '12.4', 'g/s', o ? 'dim' : null),
          tile('FUEL', o ? OFF : '62', '%', o ? 'dim' : null),
          tile('BATTERY', o ? OFF : '14.21', 'V', o ? 'dim' : null),
          tile('INSTANT', o ? OFF : '31.2', 'mpg', o ? 'dim' : null)
        ], true));
        p.body.appendChild(barBlock('Coolant', o ? 0 : 64, o ? '\u2013' : '188\u00b0F'));
        p.body.appendChild(barBlock('Intake', o ? 0 : 36, o ? '\u2013' : '97\u00b0F'));
        p.body.appendChild(barBlock('Fuel', o ? 0 : 62, o ? '\u2013' : '62%'));
        return p;
      }
    },
    {
      id: 'gforce', rail: 'G-Force', title: 'G-Force', eyebrow: 'Dynamics',
      accent: 'primary',
      build: function (o) {
        var p = panel('G-Force', 'DYNAMICS', 'primary');
        var r = el('div', 'row fill');
        r.appendChild(gaugeWrap(gforceSvg(o ? 0 : 0.42, o ? 0 : -0.18, 0.62)));
        var col = statColumn([
          ['NOW', o ? OFF : '0.46', 'g', o ? 'dim' : null],
          ['PEAK TOTAL', o ? OFF : '0.62', 'g', o ? 'dim' : 'caution'],
          ['PEAK LATERAL', o ? OFF : '0.42', 'g', o ? 'dim' : null],
          ['PEAK LONG', o ? OFF : '0.46', 'g', o ? 'dim' : null]
        ]);
        // Paired, because they are the same quantity and are read against each other.
        col.appendChild(tileRow([
          tile('LAP', o ? OFF : '1:24.60', '', o ? 'dim' : null),
          tile('BEST', o ? OFF : '1:22.15', '', o ? 'dim' : 'ok')
        ]));
        col.appendChild(barBlock('Cornering load', o ? 0 : 38, o ? '\u2013' : '0.46 g'));
        r.appendChild(col);
        p.body.appendChild(r);
        return p;
      }
    },
    {
      id: 'diag', rail: 'Diag', title: 'Diagnostics', eyebrow: 'Faults',
      accent: 'good',
      build: function (o) {
        var lamps = [
          ['CHECK ENGINE', false], ['ABS', false], ['OIL', false],
          ['BATTERY', false], ['BRAKE', false], ['AIRBAG', false],
          ['DOOR', false], ['SEATBELT', false], ['TRACTION', false]
        ];
        var p = panel('Diagnostics', 'FAULTS \u00b7 ALL CLEAR', 'good');
        for (var i = 0; i < 9; i += 3) {
          p.body.appendChild(tileRow([
            lampTile(lamps[i][0], lamps[i][1]),
            lampTile(lamps[i + 1][0], lamps[i + 1][1]),
            lampTile(lamps[i + 2][0], lamps[i + 2][1])
          ], true));
        }
        var head = el('div', 'bar-head');
        head.appendChild(el('span', null, 'Stored codes'));
        var v = el('span', 'val ok', '0 codes');
        v.style.color = 'var(--good)';
        head.appendChild(v);
        p.body.appendChild(head);
        p.body.appendChild(el('div', 'hint', 'None reported'));
        return p;
      }
    },
    {
      id: 'system', rail: 'System', title: 'System', eyebrow: 'Link',
      accent: 'accent',
      build: function (o) {
        var p = panel('System', 'LINK', 'accent');
        p.body.appendChild(tileRow([
          tile('PI LINK', o ? 'SET UP' : 'UP', '', o ? 'caution' : 'ok'),
          tile('CAN BUS', o ? 'DOWN' : 'UP', '', o ? 'fault' : 'ok'),
          tile('TPMS', o ? 'DOWN' : 'UP', '', o ? 'fault' : 'ok')
        ]));
        p.body.appendChild(tileRow([
          tile('PI SCREEN', o ? OFF : '#3', '', o ? 'dim' : null),
          tile('DEMO MODE', 'OFF', '', 'dim'),
          tile('MEMORY', '38', 'MB', null)
        ]));
        p.body.appendChild(sectionLabel('PI DISPLAY'));
        var ctrl = el('div', 'row');
        ctrl.appendChild(el('div', 'chip-button', '\u2191'));
        ctrl.appendChild(el('div', 'chip-button', '\u2193'));
        p.body.appendChild(ctrl);
        p.body.appendChild(sectionLabel('TRANSPORT'));
        ['USB tether: available', 'Bluetooth SPP: no paired device',
         'Bluetooth LE: no paired device'].forEach(function (line) {
          p.body.appendChild(el('div', 'hint', line));
        });
        return p;
      }
    },
    {
      id: 'roof', rail: 'Roof', title: 'Roof', eyebrow: 'RCNC-2',
      accent: 'primary',
      build: function (o) {
        var p = panel('Roof Controller', 'RCNC-2', 'primary');
        p.body.appendChild(tileRow([
          tile('FIRMWARE', o ? OFF : '44', '', o ? 'dim' : null),
          tile('PORT', o ? OFF : 'ttyACM0', '', o ? 'dim' : null),
          tile('STATE', o ? OFF : 'LINKED', '', o ? 'dim' : 'ok')
        ]));
        p.body.appendChild(sliderBlock('Speed limit', 30, 0, 30, 'accent'));
        p.body.appendChild(sectionLabel('MODE'));
        p.body.appendChild(chips(['One Touch', 'OEM', 'Valet'], 0));
        var spacer = el('div', 'section-label gap');
        p.body.appendChild(spacer);
        p.body.appendChild(pillRow('Auto, lower when the latch is released', true));
        p.body.appendChild(el('div', 'hint', 'One Touch for normal use. OEM restores the '
          + 'factory limits. Valet disables the roof.'));
        // The claim toggle mirrors the app's Roof screen: the label names the change it
        // performs, not the state it is in.
        var linkRow = el('div', 'row');
        linkRow.appendChild(el('div', 'chip-button',
          o ? 'Claim controller' : 'Hand back to car'));
        p.body.appendChild(linkRow);
        p.body.appendChild(el('div', 'hint', 'The RCNC-2 must be left alone for the roof to '
          + 'work normally, so hand it back when you are done.'));
        return p;
      }
    },
    {
      id: 'settings', rail: 'Setup', title: 'Settings', eyebrow: 'Configuration',
      accent: 'accent',
      build: function (o) {
        var p = panel('Settings', 'CONFIGURATION', 'accent');
        var cols = el('div', 'row');
        cols.style.flex = '1 1 auto';
        cols.style.alignItems = 'stretch';

        var left = el('div');
        left.style.cssText = 'flex:1 1 0; display:flex; flex-direction:column; min-width:0;';
        left.appendChild(sectionLabel('DISPLAY AND SOUND'));
        left.appendChild(sliderBlock('Brightness', 80, 0, 100, 'accent'));
        left.appendChild(sliderBlock('Volume', 70, 0, 100, 'accent'));
        left.appendChild(pillRow('Speed in mph', true));
        left.appendChild(pillRow('Demo mode', false));
        left.appendChild(sectionLabel('SHIFT LIGHT', true));
        left.appendChild(sliderBlock('Shift at', 6500, 3000, 8000, 'primary'));
        left.appendChild(sliderBlock('Redline', 7200, 4000, 9000, 'primary'));

        var right = el('div');
        right.style.cssText = 'flex:1 1 0; display:flex; flex-direction:column; min-width:0;';
        right.appendChild(sectionLabel('TIRE PRESSURE'));
        right.appendChild(sliderBlock('Low warning', 28, 15, 40, 'warn'));
        right.appendChild(sliderBlock('High warning', 36, 25, 55, 'warn'));
        right.appendChild(sectionLabel('ENGINE WARNING', true));
        right.appendChild(sliderBlock('Coolant warn', 220, 180, 260, 'bad'));
        right.appendChild(sectionLabel('LED STRIP', true));
        right.appendChild(chips(['Center out', 'L to R', 'R to L', 'Center in'], 0));
        right.appendChild(sectionLabel('CLUTCH DISPLAY', true));
        right.appendChild(chips(['Gear', 'C for clutch', 'S for shifting', 'Dash'], 0));

        cols.appendChild(left);
        cols.appendChild(right);
        p.body.appendChild(cols);
        return p;
      }
    }
  ];

  function lampTile(name, bad) {
    var t = el('div', 'tile lamp');
    t.appendChild(el('div', 'caption', name));
    var v = el('div', 'value', bad ? 'ON' : 'OK');
    v.style.color = bad ? 'var(--bad)' : 'var(--good)';
    t.appendChild(v);
    var dot = el('div', 'dot');
    dot.style.background = bad ? 'var(--bad)' : 'var(--good)';
    t.appendChild(dot);
    return t;
  }

  // ---------------------------------------------------------------------- shell

  /** The drawer's groups, by screen index. Mirrors MainActivity.DRAWER_GROUPS. */
  var DRAWER_GROUPS = [
    { name: 'Live', items: [0, 1, 2, 3, 4] },
    { name: 'Status', items: [5, 6] },
    { name: 'Control', items: [7, 8] }
  ];

  /**
   * Battery and clock, in the corner a system bar would have used.
   *
   * The battery is DOM rather than a glyph for the same reason BatteryIcon.java draws it: a
   * font that lacks the character is worse than no readout at all. The geometry matches the
   * Java one, including the bolt's clip-path, which is the same seven normalised points.
   */
  function buildStatusChip(opts) {
    var chip = el('div', 'status-chip');
    var level = opts.battery;

    var bat = el('div', 'battery'
      + (opts.charging ? ' charging' : (level <= 15 ? ' low' : '')));
    bat.appendChild(el('div', 'battery-body'));
    bat.appendChild(el('div', 'battery-nub'));
    var inner = el('div', 'battery-inner');
    if (level > 0) {
      var fill = el('div', 'battery-fill');
      fill.style.width = level + '%';
      inner.appendChild(fill);
    }
    bat.appendChild(inner);
    if (opts.charging) {
      bat.appendChild(el('div', 'battery-bolt'));
    }

    chip.appendChild(bat);
    chip.appendChild(el('div', 'battery-pct', level + '%'));
    chip.appendChild(el('div', 'clock', opts.clock));
    return chip;
  }

  /**
   * The phone's drawer, mirroring MainActivity.buildDrawer.
   *
   * Rendered only on request (?drawer=1). It overlays the whole shell, so it is only useful as
   * its own picture and never as a contact-sheet cell.
   */
  function buildDrawer(opts, p) {
    var host = el('div', 'drawer-host');
    host.appendChild(el('div', 'drawer-scrim'));
    var panel = el('div', 'drawer-panel');

    DRAWER_GROUPS.forEach(function (g) {
      panel.appendChild(el('div', 'drawer-group', g.name));
      g.items.forEach(function (i) {
        panel.appendChild(el('div',
          'drawer-row' + (i === opts.screenIndex ? ' on' : ''), SCREENS[i].title));
      });
    });

    panel.appendChild(el('div', 'drawer-group', 'Display'));
    panel.appendChild(el('div', 'drawer-row action', 'Scheme: ' + p.name));
    panel.appendChild(el('div', 'drawer-row action',
      'Theme: ' + (opts.mode === 'dark' ? 'dark' : 'light')));
    panel.appendChild(el('div', 'drawer-group', 'App'));
    panel.appendChild(el('div', 'drawer-row action danger', 'Exit'));

    host.appendChild(panel);
    return host;
  }

  function buildDevice(opts) {
    var device = el('div', 'device');
    var p = palette(opts.scheme, opts.mode === 'dark');
    applyTheme(device, p);

    var narrow = opts.narrow;
    device.style.flexDirection = 'column';
    if (narrow) {
      // A phone is not a car canvas. See the .device.phone rule.
      device.className = 'device phone';
    }

    // title row
    var titleRow = el('div', 'title-row');
    var current = SCREENS[opts.screenIndex];
    titleRow.appendChild(el('div', 'title-text', current.title));
    var pill = el('div', 'pill ' + (opts.offline ? 'off' : 'on'), opts.offline ? 'OFFLINE' : 'LINKED');
    titleRow.appendChild(pill);
    if (narrow) {
      // One line, like the Java: the title, the link state, and the way in. Scheme, theme,
      // battery and clock all live in the drawer or on the OS status bar.
      var ham = el('div', 'hamburger');
      for (var hb = 0; hb < 3; hb++) {
        ham.appendChild(el('span'));
      }
      titleRow.appendChild(ham);
    } else {
      titleRow.appendChild(buildStatusChip(opts));
      titleRow.appendChild(el('div', 'chip-button', p.name));
      titleRow.appendChild(el('div', 'chip-button', opts.mode === 'dark' ? 'Dark' : 'Light'));
      titleRow.appendChild(el('div', 'exit-button', 'Exit'));
    }
    device.appendChild(titleRow);

    // body: a left rail on the car. Nothing on a phone: the drawer carries navigation there,
    // so there is no strip of chips under the title any more.
    var body = el('div', 'body');
    if (!narrow) {
      var rail = el('div', 'rail');
      SCREENS.forEach(function (s, i) {
        var item = el('div', 'rail-item' + (i === opts.screenIndex ? ' on' : ''));
        item.appendChild(el('div', 'marker'));
        item.appendChild(el('span', null, s.rail));
        rail.appendChild(item);
      });
      body.appendChild(rail);
    }

    var content = el('div', 'content');
    content.appendChild(current.build(opts.offline));
    body.appendChild(content);
    device.appendChild(body);

    // footer
    var footer = el('div', 'footer');
    footer.appendChild(el('div', 'footer-hairline'));
    var frow = el('div', 'footer-row');
    frow.appendChild(el('span', null, opts.narrow ? 'BLUETOOTH SPP'
      : (opts.offline ? 'No Pi set up, see System' : 'http://192.168.42.100:5000')));
    var state = opts.offline ? 'OFFLINE' : 'LIVE';
    frow.appendChild(el('span', 'right', state + '  \u00b7  ' + (opts.offline ? 0 : 3120) + ' rpm'));
    footer.appendChild(frow);
    device.appendChild(footer);

    if (narrow && opts.drawer) {
      device.appendChild(buildDrawer(opts, p));
    }
    return device;
  }

  /**
   * Put the mimic on the page: one screen, or all nine at half scale.
   *
   * The contact sheet exists because judging one screen at a time hides the thing that
   * actually matters for consistency, which is whether the nine look like one app.
   */
  function present(opts) {
    document.body.innerHTML = '';

    if (opts.all) {
      var sheet = el('div', 'sheet');
      SCREENS.forEach(function (s, i) {
        var cell = el('div', 'sheet-cell');
        cell.appendChild(el('div', 'sheet-label', s.title));
        var frame = el('div', 'sheet-frame');
        frame.appendChild(buildDevice({
          screenIndex: i,
          scheme: opts.scheme,
          mode: opts.mode,
          narrow: false,
          offline: opts.offline
        }));
        cell.appendChild(frame);
        sheet.appendChild(cell);
      });
      document.body.appendChild(sheet);
      return;
    }

    document.body.appendChild(buildDevice(opts));
  }

  // ----------------------------------------------------------------------- boot

  function params() {
    var q = new URLSearchParams(location.search);
    var id = q.get('screen') || 'overview';
    var idx = 0;
    SCREENS.forEach(function (s, i) { if (s.id === id || s.rail.toLowerCase() === id.toLowerCase()) { idx = i; } });
    var bat = parseInt(q.get('battery'), 10);
    return {
      screenIndex: idx,
      scheme: q.get('scheme') || 'aurora',
      mode: q.get('mode') === 'light' ? 'light' : 'dark',
      narrow: q.get('narrow') === '1',
      offline: q.get('offline') === '1',
      all: q.get('all') === '1',
      drawer: q.get('drawer') === '1',
      // Both are overridable so a screenshot is reproducible. A real clock in a screenshot
      // makes two runs differ for no reason, which is how a real regression gets missed.
      battery: isNaN(bat) ? 72 : bat,
      charging: q.get('charging') === '1',
      clock: q.get('clock') || clockNow()
    };
  }

  function clockNow() {
    var d = new Date();
    return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
  }

  window.MX5_MIMIC = {
    build: buildDevice,
    present: present,
    screens: SCREENS,
    palette: palette,
    params: params
  };
  present(params());
})();
