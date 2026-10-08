"""Inject (or replace) an 'openloop' tab into buck.drawio with embedded waveform PNG."""
import base64
import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT       = Path(__file__).resolve().parent.parent
DRAWIO     = ROOT / "buck.drawio"
PNG        = ROOT / "buck" / "buck_plant_waveform.png"

STEPS_HTML = """<div style="font-family:Arial;font-size:12px;line-height:1.5;padding:6px;">
<b style="font-size:14px;">Test Steps</b>
<ol style="margin:4px 0 8px 20px;padding:0;">
<li>Reset held, released at t = 100 ns.</li>
<li>PWM at f<sub>sw</sub> = 100 kHz with duty = 50 % — settle for 3 ms (dominant τ = R<sub>load</sub>·C = 600 µs).</li>
<li>Step duty 50 % → 75 % at t = 3 ms — settle for 5 ms.</li>
<li>State update every Δt = 100 ns (Forward Euler, Q8.24 fixed-point). VCD dumped, parsed by plot_waveform.py → PNG below.</li>
</ol>
<b style="font-size:14px;">Setpoint check</b> &nbsp;<span style="font-size:11px;color:#555;">V<sub>out</sub> = d · V<sub>in</sub> / (1 + R<sub>L</sub>/R<sub>load</sub>) = 0.9917 · d · V<sub>in</sub></span>
<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse;font-size:11px;margin-top:4px;width:70%;">
<tr style="background:#e8e8e8;font-weight:bold;">
<th style="padding:4px;border:1px solid #000;">Phase</th>
<th style="padding:4px;border:1px solid #000;">Duty</th>
<th style="padding:4px;border:1px solid #000;">V<sub>out</sub> target</th>
<th style="padding:4px;border:1px solid #000;">V<sub>out</sub> observed</th>
<th style="padding:4px;border:1px solid #000;">Error</th>
</tr>
<tr>
<td style="padding:4px;border:1px solid #000;text-align:center;">A &nbsp;(t = 3 ms)</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">50 %</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">11.901 V</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">11.891 V</td>
<td style="padding:4px;border:1px solid #000;text-align:center;color:#1b7a1b;font-weight:bold;">0.08 %</td>
</tr>
<tr>
<td style="padding:4px;border:1px solid #000;text-align:center;">B &nbsp;(t = 8 ms)</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">75 %</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">17.851 V</td>
<td style="padding:4px;border:1px solid #000;text-align:center;">17.830 V</td>
<td style="padding:4px;border:1px solid #000;text-align:center;color:#1b7a1b;font-weight:bold;">0.12 %</td>
</tr>
</table>
<div style="margin-top:8px;font-size:11px;">
<b>Dynamic signature observed:</b> very underdamped LC — ζ ≈ 0.025, Q ≈ 20 → f<sub>n</sub> ≈ 1.59 kHz, ring period ≈ 629 µs, ~5 overshoot cycles before settling. Switching ripple (100 kHz) visible as trace thickness on i<sub>L</sub>.
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
        '  <diagram name="openloop" id="openloop_tab">\n'
        '    <mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" '
        'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="900" pageHeight="970" '
        'math="0" shadow="0">\n'
        '      <root>\n'
        '        <mxCell id="o0" />\n'
        '        <mxCell id="o1" parent="o0" />\n'
        '        <mxCell id="ol_title" value="Open-Loop Plant Verification" '
        'style="text;html=1;align=center;verticalAlign=middle;fontSize=20;fontStyle=1;" '
        'vertex="1" parent="o1">\n'
        '          <mxGeometry x="200" y="20" width="500" height="34" as="geometry" />\n'
        '        </mxCell>\n'
        '        <mxCell id="ol_subtitle" value="Synchronous Buck — 8 ms switched sim: '
        'Vin=24 V, L=100 µH, C=100 µF, R_L=50 mΩ, R_load=6 Ω, f_sw=100 kHz, Δt=100 ns" '
        'style="text;html=1;align=center;verticalAlign=middle;fontSize=11;fontStyle=2;'
        'fontColor=#555555;" vertex="1" parent="o1">\n'
        '          <mxGeometry x="30" y="56" width="840" height="20" as="geometry" />\n'
        '        </mxCell>\n'
        f'        <mxCell id="ol_steps" value="{steps_val}" '
        'style="text;html=1;strokeColor=#B5B5B5;fillColor=#F8F8F8;align=left;verticalAlign=top;'
        'whiteSpace=wrap;rounded=1;overflow=hidden;" vertex="1" parent="o1">\n'
        '          <mxGeometry x="40" y="90" width="820" height="320" as="geometry" />\n'
        '        </mxCell>\n'
        f'        <mxCell id="ol_image" value="" '
        f'style="shape=image;html=1;imageAspect=1;image={img_data_uri}" '
        'vertex="1" parent="o1">\n'
        '          <mxGeometry x="40" y="430" width="820" height="520" as="geometry" />\n'
        '        </mxCell>\n'
        '      </root>\n'
        '    </mxGraphModel>\n'
        '  </diagram>\n'
    )

    text = DRAWIO.read_text(encoding="utf-8")

    # Remove any prior openloop tab so we can re-run idempotently
    text = re.sub(
        r'  <diagram name="openloop".*?</diagram>\s*',
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
