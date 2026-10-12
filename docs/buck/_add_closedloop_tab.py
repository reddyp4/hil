"""Inject (or replace) a 'closedloop' tab into buck.drawio with embedded waveform PNG."""
import base64
import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT   = Path(__file__).resolve().parent.parent
DRAWIO = ROOT / "buck.drawio"
PNG    = ROOT / "buck" / "buck_closed_waveform.png"

STEPS_HTML = """<div style="font-family:Arial;font-size:12px;line-height:1.5;padding:6px;">
<b style="font-size:14px;">Test Steps</b>
<ol style="margin:4px 0 8px 20px;padding:0;">
<li>Reset held, released at t = 200 ns. v_ref initialised to 12 V.</li>
<li>Settle at v_ref = 12 V for 5 ms (startup).</li>
<li>Step v_ref 12 V → 18 V at t = 5 ms, hold for 5 ms (reference-step response).</li>
<li>Plant and controller share the same clk and tick; PI fires once per PWM period (every 10 µs).</li>
</ol>
<b style="font-size:14px;">PI gains</b> &nbsp;<span style="font-size:11px;color:#555;">inner ω<sub>c</sub> ≈ 2π·10 kHz, outer ω<sub>c</sub> ≈ 2π·1 kHz, Ti = 1/ω<sub>c</sub> on each loop</span>
<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse;font-size:11px;margin:4px 0 8px 0;width:60%;">
<tr style="background:#e8e8e8;font-weight:bold;">
<th style="padding:4px;border:1px solid #000;">Gain</th>
<th style="padding:4px;border:1px solid #000;">Definition</th>
<th style="padding:4px;border:1px solid #000;">Real value</th>
</tr>
<tr><td style="padding:4px;border:1px solid #000;text-align:center;">KP<sub>V</sub></td><td style="padding:4px;border:1px solid #000;">ω<sub>c</sub> · C</td><td style="padding:4px;border:1px solid #000;text-align:center;">0.628 A/V</td></tr>
<tr><td style="padding:4px;border:1px solid #000;text-align:center;">KI<sub>V</sub></td><td style="padding:4px;border:1px solid #000;">KP<sub>V</sub> · Ts/Ti</td><td style="padding:4px;border:1px solid #000;text-align:center;">0.0395 per Ts</td></tr>
<tr><td style="padding:4px;border:1px solid #000;text-align:center;">KP<sub>I</sub></td><td style="padding:4px;border:1px solid #000;">ω<sub>c</sub> · L / V<sub>in</sub></td><td style="padding:4px;border:1px solid #000;text-align:center;">0.262</td></tr>
<tr><td style="padding:4px;border:1px solid #000;text-align:center;">KI<sub>I</sub></td><td style="padding:4px;border:1px solid #000;">KP<sub>I</sub> · Ts/Ti</td><td style="padding:4px;border:1px solid #000;text-align:center;">0.164 per Ts</td></tr>
</table>
<b style="font-size:14px;">Setpoint tracking</b> &nbsp;<span style="font-size:11px;color:#555;">closed-loop: integrator absorbs R<sub>L</sub> drop → zero steady-state error</span>
<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse;font-size:11px;margin-top:4px;width:70%;">
<tr style="background:#e8e8e8;font-weight:bold;">
<th style="padding:4px;border:1px solid #000;">Phase</th>
<th style="padding:4px;border:1px solid #000;">v<sub>ref</sub></th>
<th style="padding:4px;border:1px solid #000;">v<sub>C</sub> observed</th>
<th style="padding:4px;border:1px solid #000;">Error</th>
<th style="padding:4px;border:1px solid #000;">i<sub>L</sub> avg</th>
<th style="padding:4px;border:1px solid #000;">duty avg</th>
</tr>
<tr>
<td style="padding:4px;border:1px solid #000;text-align:center;">A &nbsp;(t=5 ms)</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">12 V</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">12.0003 V</td>
<td style="padding:4px;border:1px solid #000;text-align:center;color:#1b7a1b;font-weight:bold;">0.003 %</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">1.73 A</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">0.512</td>
</tr>
<tr>
<td style="padding:4px;border:1px solid #000;text-align:center;">B &nbsp;(t=10 ms)</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">18 V</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">18.0002 V</td>
<td style="padding:4px;border:1px solid #000;text-align:center;color:#1b7a1b;font-weight:bold;">0.001 %</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">2.82 A</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">0.761</td>
</tr>
</table>
<div style="margin-top:8px;font-size:11px;">
<b>Dynamic signature observed:</b> startup overshoots ~21 % (v_C peaks ~14.5 V) then settles by t ≈ 1 ms; reference-step 12 → 18 V settles by t ≈ 6 ms with minimal overshoot. Duty saturates to 1.0 briefly on both transients and anti-windup prevents post-saturation hangover.
</div>
</div>"""


def main():
    if not PNG.exists():
        raise SystemExit(f"PNG not found: {PNG}")
    if not DRAWIO.exists():
        raise SystemExit(f"drawio not found: {DRAWIO}")

    b64 = base64.b64encode(PNG.read_bytes()).decode("ascii")
    img_data_uri = f"data:image/png,{b64}"

    steps_val = escape(STEPS_HTML, {'"': "&quot;"})

    new_diagram = (
        '  <diagram name="closedloop" id="closedloop_tab">\n'
        '    <mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" '
        'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="900" pageHeight="1120" '
        'math="0" shadow="0">\n'
        '      <root>\n'
        '        <mxCell id="c0" />\n'
        '        <mxCell id="c1" parent="c0" />\n'
        '        <mxCell id="cl_title" value="Closed-Loop Verification (Plant + Cascaded PI)" '
        'style="text;html=1;align=center;verticalAlign=middle;fontSize=20;fontStyle=1;" '
        'vertex="1" parent="c1">\n'
        '          <mxGeometry x="140" y="20" width="620" height="34" as="geometry" />\n'
        '        </mxCell>\n'
        '        <mxCell id="cl_subtitle" value="Synchronous Buck — 10 ms sim: v_ref step 12 V → 18 V; '
        'inner ω_c≈10 kHz, outer ω_c≈1 kHz, Δt=100 ns, Q8.24 fixed-point" '
        'style="text;html=1;align=center;verticalAlign=middle;fontSize=11;fontStyle=2;'
        'fontColor=#555555;" vertex="1" parent="c1">\n'
        '          <mxGeometry x="30" y="56" width="840" height="20" as="geometry" />\n'
        '        </mxCell>\n'
        f'        <mxCell id="cl_steps" value="{steps_val}" '
        'style="text;html=1;strokeColor=#B5B5B5;fillColor=#F8F8F8;align=left;verticalAlign=top;'
        'whiteSpace=wrap;rounded=1;overflow=hidden;" vertex="1" parent="c1">\n'
        '          <mxGeometry x="40" y="90" width="820" height="470" as="geometry" />\n'
        '        </mxCell>\n'
        f'        <mxCell id="cl_image" value="" '
        f'style="shape=image;html=1;imageAspect=1;image={img_data_uri}" '
        'vertex="1" parent="c1">\n'
        '          <mxGeometry x="40" y="580" width="820" height="520" as="geometry" />\n'
        '        </mxCell>\n'
        '      </root>\n'
        '    </mxGraphModel>\n'
        '  </diagram>\n'
    )

    text = DRAWIO.read_text(encoding="utf-8")

    # Strip any prior closedloop tab so re-runs replace cleanly
    text = re.sub(
        r'  <diagram name="closedloop".*?</diagram>\s*',
        '',
        text,
        flags=re.DOTALL,
    )

    if "</mxfile>" not in text:
        raise SystemExit("Could not find </mxfile> in drawio.")
    text = text.replace("</mxfile>", new_diagram + "</mxfile>")

    DRAWIO.write_text(text, encoding="utf-8")
    print(f"wrote {DRAWIO}  ({len(text)/1024:.1f} KB)  (image base64 {len(b64)/1024:.1f} KB)")


if __name__ == "__main__":
    main()
